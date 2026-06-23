"""Resolve named workflow components selected by a minimal experiment YAML.

The resolver has no renderer, scheduler or runtime side effects. It provides a
small, explicit contract for composing future cyclic experiments while leaving
the existing baseline loader untouched.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .yaml_utils import load_yaml_file


COMPONENT_SELECTIONS: dict[str, tuple[str, str]] = {
    "assimilation": ("assimilation", "method"),
    "forecast": ("forecast", "profile"),
    "background": ("background", "source"),
    "bmatrix": ("bmatrix", "name"),
    "geometry": ("geometry", "name"),
    "site": ("run", "site"),
    "observations": ("observations", "set"),
}


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{context} must be a YAML mapping")
    return value


def _safe_component_name(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(f"Invalid component name: {name!r}")
    return name


def _selected_site(section: dict[str, Any]) -> str:
    site = section.get("site")
    platform = section.get("platform")
    if site is not None and platform is not None and site != platform:
        raise ValueError("run.site and run.platform select different targets")
    selected = site if site is not None else platform
    if not isinstance(selected, str):
        raise TypeError("run.site must be a component name string")
    return selected


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge mappings recursively; scalars and lists in override replace base."""
    merged = deepcopy(base)
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = deep_merge(base_value, override_value)
        else:
            merged[key] = deepcopy(override_value)
    return merged


class ComponentRepository:
    """Filesystem-backed repository of named YAML workflow components."""

    def __init__(self, config_root: Path) -> None:
        self.config_root = config_root.resolve()

    def load(self, category: str, name: str) -> dict[str, Any]:
        """Load ``configs/<category>/<name>.yaml`` and validate its mapping form."""
        component_name = _safe_component_name(name)
        path = self.config_root / category / f"{component_name}.yaml"
        if not path.is_file():
            raise FileNotFoundError(
                f"Unknown {category} component {component_name!r}: {path}"
            )
        return load_yaml_file(path)


def infer_config_root(experiment_path: Path) -> Path:
    """Infer ``configs`` from a file located under ``configs/experiments``."""
    resolved = experiment_path.resolve()
    if resolved.parent.name != "experiments" or resolved.parent.parent.name != "configs":
        raise ValueError(
            "Experiment must be located directly under configs/experiments to infer config root"
        )
    return resolved.parent.parent


def resolve_experiment_components(
    experiment_path: Path,
    *,
    config_root: Path | None = None,
) -> dict[str, Any]:
    """Resolve component selections from a minimal experiment YAML."""
    experiment = load_yaml_file(experiment_path)
    root = config_root.resolve() if config_root is not None else infer_config_root(experiment_path)
    repository = ComponentRepository(root)
    components: dict[str, dict[str, Any]] = {}

    for label, (section_name, key_name) in COMPONENT_SELECTIONS.items():
        section = _require_mapping(experiment.get(section_name), section_name)
        selected = _selected_site(section) if label == "site" else section.get(key_name)
        if not isinstance(selected, str):
            raise TypeError(f"{section_name}.{key_name} must be a component name string")
        category = "sites" if label == "site" else label
        components[label] = repository.load(category, selected)

    # Backward-compatible alias while older tests and callers still refer to the
    # selected execution environment as ``platform``.
    components["platform"] = {
        **components["site"],
        "platform": components["site"]["site"],
    }

    return {
        "experiment": experiment,
        "components": components,
    }
