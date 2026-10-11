"""Generic filesystem/YAML helpers for scientific case materialization."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from .stage_config import StageConfigurationError

_FORBIDDEN_CASE_NAMES = ("jedi.stdout.log", "jedi.stderr.log", "stdout.log", "stderr.log")
_FORBIDDEN_CASE_PREFIXES = ("mpasout.", "obsout_")


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise StageConfigurationError(f"YAML root must be a mapping: {path}")
    return value


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def assert_clean_case_tree(root: Path, *, excluded: Path | None = None) -> None:
    for directory, names, files in os.walk(root, followlinks=False):
        if excluded is not None:
            names[:] = [name for name in names if Path(directory) / name != excluded]
        for name in names + files:
            _assert_clean_case_path(Path(directory) / name)


def _assert_clean_case_path(path: Path) -> None:
    if ".monan-jedi-workflow" in path.parts:
        raise StageConfigurationError(
            f"source case contains runtime control state and is not clean: {path}"
        )
    if not path.is_file() and not path.is_symlink():
        return
    if path.name in _FORBIDDEN_CASE_NAMES or path.name.startswith(_FORBIDDEN_CASE_PREFIXES):
        raise StageConfigurationError(
            f"source case contains a runtime/scientific product: {path}"
        )


def copy_clean_case(source: Path, destination: Path) -> None:
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"source case directory does not exist: {source}")
    destination = destination.resolve()
    if destination == source:
        raise StageConfigurationError("case destination must differ from the source case")
    # Campaign storage is not part of the template. Exclude its top-level
    # subtree before validation and copying, including previous campaigns.
    relative = destination.relative_to(source) if source in destination.parents else None
    excluded = source / relative.parts[0] if relative is not None else None
    assert_clean_case_tree(source, excluded=excluded)

    def ignore(directory: str, names: list[str]) -> list[str]:
        if Path(directory) == source and excluded is not None:
            return [excluded.name] if excluded.name in names else []
        return []

    shutil.copytree(source, destination, symlinks=True, ignore=ignore)


def absolutize_case_path(value: Any, source_case: Path) -> Any:
    if not isinstance(value, str) or not value:
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((source_case.resolve() / path).resolve(strict=False))
