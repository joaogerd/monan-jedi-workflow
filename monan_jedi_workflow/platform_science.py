"""Compose explicit native JEDI application and ordered observer fragments."""

from copy import deepcopy
from pathlib import Path
import textwrap
import yaml
from .platform_config import read_yaml, reference


def overrides(original, changes, path="application"):
    result = deepcopy(original)
    if not isinstance(changes, dict):
        raise ValueError(f"{path} overrides must be a mapping")
    for key, value in changes.items():
        if key not in result:
            raise ValueError(f"unknown override key {path}.{key}")
        if isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = overrides(result[key], value, f"{path}.{key}")
        else:
            result[key] = deepcopy(value)
    return result


def selection(document, base):
    config = document.get("observations", {})
    if not isinstance(config, dict):
        raise ValueError("observations must be a mapping")
    use = config.get("use")
    if use is not None and (
        not isinstance(use, list)
        or not use
        or len(set(use)) != len(use)
        or any(
            not isinstance(v, str) or not v.replace("_", "").replace("-", "").isalnum()
            for v in use
        )
    ):
        raise ValueError("observations.use requires distinct plain observer names")
    return config


def compose_application(section, document, base):
    if "application" not in section:
        return
    application_path = reference(section["application"], base)
    application = read_yaml(application_path)
    application = overrides(application, section.get("application_overrides", {}))
    obs = selection(document, base)
    if obs.get("use"):
        directory = reference(obs["configure"], base)
        chunks = []
        for anchor in obs.get("anchors", []):
            chunks.append(reference(anchor, directory).read_text())
        chunks.append("observers:\n")
        for name in obs["use"]:
            raw = (directory / "da/base" / f"{name}.yaml").read_text()
            filters = (directory / "da/filters" / f"{name}.yaml").read_text()
            chunks.append(
                "  -\n"
                + textwrap.indent(raw.rstrip() + "\n" + filters.rstrip() + "\n", "    ")
            )
        combined = yaml.safe_load("\n".join(chunks))
        application.setdefault("cost function", {}).setdefault("observations", {})[
            "observers"
        ] = combined["observers"]
    section["_resolved_application"] = application
    section["_application_target"] = section.get(
        "application_target", "variational.yaml"
    )
    target = Path(section["_application_target"])
    if target.is_absolute() or ".." in target.parts:
        raise ValueError("application_target must be inside the runtime")
    # Preserve native science in the lock; generated template is an implementation detail.
    section.pop("application", None)
    section.pop("application_overrides", None)


def select_products(section, document, key):
    obs = selection(document, None)
    if not obs.get("use") or key not in {"obs2ioda", "acquisition"}:
        return
    products = obs.get("products")
    if not isinstance(products, dict):
        raise ValueError(
            "observations.products must associate selected observers with converter/acquisition names"
        )
    role = "converter" if key == "obs2ioda" else "acquisition"
    names = set()
    for name in obs["use"]:
        if name not in products or role not in products[name]:
            raise ValueError(f"observations.products.{name}.{role} is required")
        names.add(products[name][role])
    field = "converters" if key == "obs2ioda" else "sources"
    entries = section.get(field, [])
    section[field] = [v for v in entries if v.get("name") in names]
    missing = names - {v["name"] for v in section[field]}
    if missing:
        raise ValueError(f"missing selected {role}: {sorted(missing)}")
