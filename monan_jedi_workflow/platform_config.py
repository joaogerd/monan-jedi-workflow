"""Resolve only the requested domain and preserve configuration provenance."""

from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
import json
import os
import re
import yaml
from copy import deepcopy
from .cycle_context import parse_cycle_time


def read_yaml(path):
    value = yaml.safe_load(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected YAML mapping")
    return value


def expand(value):
    if isinstance(value, dict):
        return {k: expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v) for v in value]
    if isinstance(value, str):
        result = os.path.expandvars(value)
        if re.search(r"\$(?:\{|[A-Za-z_])", result):
            raise ValueError(f"undefined environment variable in {value}")
        return result
    return value


def reference(value, base):
    if not isinstance(value, str) or not value:
        raise ValueError("configuration reference must be a nonempty path")
    if re.match(r"^\{[A-Za-z_][A-Za-z0-9_]*\}(?:/|$)", value):
        return value
    if value.startswith("catalog:"):
        name = value[8:]
        if ".." in Path(name).parts or Path(name).is_absolute():
            raise ValueError("catalog path must stay inside installed catalog")
        return Path(str(files("monan_jedi_workflow").joinpath("catalog", name)))
    path = Path(expand(value)).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class Operation:
    principal: Path
    root: Path
    config: dict
    site: dict
    section: dict
    domain_file: Path
    key: str
    filename: str
    identity: str
    sources: dict


def load_operation(request):
    principal = request.config.resolve()
    config = read_yaml(principal)
    if config.get("schema_version") != 1:
        raise ValueError("experiment schema_version must be 1")
    experiment = config.get("experiment", {})
    if not isinstance(experiment, dict) or not experiment.get("name"):
        raise ValueError("experiment.name is required")
    destination = experiment.get("destination")
    if not isinstance(destination, str) or not destination:
        raise ValueError("experiment.destination is required")
    root = reference(destination, principal.parent)
    if not isinstance(root, Path):
        raise ValueError(
            "experiment.destination must be a static path; use environment variables for roots"
        )
    raw_site = config.get("site", {})
    sources = {str(principal): config}
    if isinstance(raw_site, str):
        path = reference(raw_site, principal.parent)
        site = read_yaml(path)
        sources[str(path)] = site
        site = site.get("site", site)
    else:
        site = raw_site
    if not isinstance(site, dict):
        raise ValueError("site must be a mapping or a file reference")
    if request.app == "obs":
        selection = config.get("observations", config.get("jedi"))
        key = "acquisition" if request.operation == "acquire" else "obs2ioda"
        filename = "acquisition.yaml" if key == "acquisition" else "obs2ioda.yaml"
    elif request.app == "mpas":
        selection = config.get("mpas")
        key = "mpas_init" if request.operation == "init" else "mpas"
        filename = key + ".yaml"
    else:
        key = request.app
        selection = config.get(key)
        filename = key + ".yaml"
    document = {}
    if isinstance(selection, str):
        domain_file = reference(selection, principal.parent)
        document = read_yaml(domain_file)
        sources[str(domain_file)] = document
        section = document.get(key)
    elif isinstance(selection, dict):
        domain_file = principal
        section = selection.get(key, selection)
    else:
        raise ValueError(f"{request.app}: configuration reference is required")
    if not isinstance(section, dict):
        raise ValueError(f"{domain_file}: mapping {key} is required")
    section = deepcopy(section)
    from .platform_science import compose_application, select_products

    metadata = document.get("observations", {})
    if not isinstance(metadata, dict):
        raise ValueError("observations must be a mapping")
    wanted = (
        ("use", "products")
        if key in {"obs2ioda", "acquisition"}
        else ("use", "configure", "anchors")
    )
    selected_document = {
        "observations": expand({k: v for k, v in metadata.items() if k in wanted})
    }
    select_products(section, selected_document, key)
    section = expand(section)
    if key == "jedi":
        compose_application(section, selected_document, domain_file.parent)
    # Machine profiles may describe all apps. Resolve only this domain's
    # resources and referenced variables (including variables used in templates).
    resource = site.get("resources", {}).get(key, {})
    if resource:
        section["pbs"] = {**resource, **section.get("pbs", {})}
    text = json.dumps(section)
    for entry in section.get("templates", []):
        candidate = Path(str(reference(entry["source"], domain_file.parent)))
        if candidate.is_file():
            text += candidate.read_text()
    needed = set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", text))
    available = site.get("variables", {})
    selected_variables = {}
    while True:
        new = (
            needed.intersection(available)
            .difference(selected_variables)
            .difference(section.get("variables", {}))
        )
        if not new:
            break
        for name in new:
            selected_variables[name] = available[name]
            needed.update(
                re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", str(available[name]))
            )
    site = expand(
        {
            "execution": site.get("execution", {}),
            "variables": selected_variables,
            "resources": {key: resource} if resource else {},
        }
    )
    # Paths used as external sources retain their declaring-file origin.
    for name in ("links", "templates", "link_directories"):
        items = section.get(name, [])
        for i, item in enumerate(items):
            if isinstance(item, dict) and "source" in item:
                item["source"] = str(reference(item["source"], domain_file.parent))
            elif name == "link_directories" and isinstance(item, str):
                items[i] = str(reference(item, domain_file.parent))
    for name in ("background", "analysis_base_state", "runtime_skeleton"):
        value = section.get(name)
        if isinstance(value, dict):
            for field in ("source", "initial_source"):
                if field in value:
                    value[field] = str(reference(value[field], domain_file.parent))
        elif isinstance(value, str):
            section[name] = str(reference(value, domain_file.parent))
    if isinstance(section.get("runtime"), dict) and "skeleton" in section["runtime"]:
        section["runtime"]["skeleton"] = str(
            reference(section["runtime"]["skeleton"], domain_file.parent)
        )
    if key == "obs2ioda":
        for converter in section.get("converters", []):
            converter["inputs"] = [
                str(reference(v, domain_file.parent))
                for v in converter.get("inputs", [])
            ]
            converter["outputs"] = [
                str(reference(v, root)) for v in converter.get("outputs", [])
            ]
    for field in ("run_dir", "work_dir"):
        if field in section:
            section[field] = str(reference(section[field], root))
    if key == "mpas_init":
        validation = section.get("validation", {})
        validation["required_outputs"] = [
            (
                str(Path(section["run_dir"]) / v)
                if not Path(v).is_absolute() and not v.startswith("{")
                else v
            )
            for v in validation.get("required_outputs", [])
        ]
    section.setdefault("variables", {})
    section["variables"].setdefault("experiment_root", str(root))
    section["variables"].setdefault("configuration_root", str(domain_file.parent))
    pending = dict(site.get("variables", {}))
    ordered = {}
    while pending:
        ready = [
            name
            for name, value in pending.items()
            if not set(
                re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", str(value))
            ).intersection(pending)
        ]
        if not ready:
            raise ValueError("cyclic site variable dependency")
        for name in ready:
            ordered[name] = pending.pop(name)
    section["variables"] = {**ordered, **section["variables"]}
    resource = site.get("resources", {}).get(key, {})
    if resource:
        section["pbs"] = {**resource, **section.get("pbs", {})}
    section = expand(section)
    # Templates are part of scientific identity, not just their filenames.
    assets = {}
    for entry in section.get("templates", []):
        path = Path(entry["source"])
        if path.is_file():
            assets[str(path)] = sha256(path.read_bytes()).hexdigest()
    identity = digest(
        {
            "platform_version": "0.3.0b1",
            "experiment": experiment,
            "section": section,
            "site": site,
            "assets": assets,
            "app": request.app,
            "operation": request.operation,
            "cycle": parse_cycle_time(request.cycle).cycle_time,
            "source": request.source,
        }
    )
    return Operation(
        principal,
        root,
        config,
        site,
        section,
        domain_file,
        key,
        filename,
        identity,
        sources,
    )
