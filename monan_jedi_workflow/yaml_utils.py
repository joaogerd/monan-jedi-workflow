"""YAML loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file and require a mapping at the top level."""
    if not path.is_file():
        raise FileNotFoundError(f"YAML file not found: {path}")

    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise TypeError(f"YAML file must contain a top-level mapping: {path}")

    return data
