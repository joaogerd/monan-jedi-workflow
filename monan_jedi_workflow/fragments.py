from __future__ import annotations

from pathlib import Path
from typing import Any

from .yaml_utils import load_yaml_file


OBSERVER_FRAGMENT_DIR = Path("configs/fragments/jedi/observers")


def get_project_root(config_dir: Path) -> Path:
    return config_dir.resolve().parents[2]


def resolve_observer_fragment(config_dir: Path, name: str) -> dict[str, Any]:
    fragment_path = get_project_root(config_dir) / OBSERVER_FRAGMENT_DIR / f"{name}.yaml"
    fragment = load_yaml_file(fragment_path)
    observer = fragment.get("observer")
    if not isinstance(observer, dict):
        raise TypeError(f"Expected mapping key 'observer' in {fragment_path}")
    return observer


def resolve_observation_config(config_dir: Path, observations: dict[str, Any]) -> dict[str, Any]:
    if "observers" in observations:
        return observations

    selector = observations.get("observations")
    if not isinstance(selector, dict):
        raise KeyError("observations.yaml must contain 'observers' or 'observations'")

    selected = selector.get("use")
    if not isinstance(selected, list) or not selected:
        raise ValueError("observations.use must be a non-empty list")

    return {
        "observers": [
            resolve_observer_fragment(config_dir, str(name))
            for name in selected
        ]
    }
