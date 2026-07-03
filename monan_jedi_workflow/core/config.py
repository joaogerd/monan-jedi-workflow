"""Configuration loading, composition, and resolved-config persistence."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    """Raised when a configuration file or composition is invalid."""


def load_mapping(path: Path) -> dict[str, Any]:
    """Load one YAML mapping.

    Parameters
    ----------
    path : Path
        YAML file to load.

    Returns
    -------
    dict[str, Any]
        Parsed top-level mapping. Empty YAML files produce an empty mapping.

    Raises
    ------
    ConfigurationError
        Raised when the file is absent or its top-level value is not a mapping.
    """
    if not path.is_file():
        raise ConfigurationError(f"Configuration file is missing: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ConfigurationError(f"Configuration must be a top-level mapping: {path}")
    return payload


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge one configuration mapping over another.

    Parameters
    ----------
    base : Mapping[str, Any]
        Lower-precedence configuration mapping.
    override : Mapping[str, Any]
        Higher-precedence configuration mapping.

    Returns
    -------
    dict[str, Any]
        New merged mapping without mutation of either input.

    Notes
    -----
    Mappings merge recursively. Lists and scalar values replace the lower-
    precedence value in full so list ordering remains explicit in YAML.
    """
    result = deepcopy(dict(base))
    for key, value in override.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(current, value)
        else:
            result[key] = deepcopy(value)
    return result


def resolve_configuration(paths: list[Path]) -> dict[str, Any]:
    """Load and merge ordered configuration layers.

    Parameters
    ----------
    paths : list[Path]
        Configuration paths ordered from lowest to highest precedence.

    Returns
    -------
    dict[str, Any]
        Fully resolved configuration mapping.

    Raises
    ------
    ConfigurationError
        Raised when no paths are supplied or one layer is invalid.
    """
    if not paths:
        raise ConfigurationError("At least one configuration layer is required.")
    resolved: dict[str, Any] = {}
    for path in paths:
        resolved = deep_merge(resolved, load_mapping(path))
    return resolved


def write_resolved_configuration(path: Path, config: Mapping[str, Any]) -> Path:
    """Write the exact resolved configuration used by a workflow run.

    Parameters
    ----------
    path : Path
        Destination YAML path inside the run workspace.
    config : Mapping[str, Any]
        Fully resolved configuration mapping.

    Returns
    -------
    Path
        Written configuration path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(config), sort_keys=False), encoding="utf-8")
    return path
