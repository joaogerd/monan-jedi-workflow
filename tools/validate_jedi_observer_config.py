#!/usr/bin/env python3
"""Validate rendered JEDI observer configuration against experiment manifests.

This is a structural validator. It checks whether the rendered JEDI YAML contains
observers expected by the experiment observer manifest and IODA inventory.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def observer_manifest_names(path: Path) -> list[str]:
    data = read_yaml(path)
    root = data.get("observers") if isinstance(data, dict) else None
    if not isinstance(root, list):
        raise ValueError("observer manifest must contain observers list")
    names: list[str] = []
    for item in root:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(str(item["name"]))
    return names


def ioda_inventory_names(path: Path) -> list[str]:
    data = read_yaml(path)
    root = data.get("ioda_inventory") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        raise ValueError("IODA inventory must contain ioda_inventory mapping")
    entries = root.get("observations", root.get("files", []))
    if not isinstance(entries, list):
        raise ValueError("IODA inventory observations/files must be a list")
    names: list[str] = []
    for item in entries:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(str(item["name"]))
    return names


def collect_observers(node: Any) -> list[dict[str, Any]]:
    """Find observer dictionaries in a rendered JEDI YAML tree."""
    found: list[dict[str, Any]] = []

    if isinstance(node, dict):
        obs_space = node.get("obs space")
        if isinstance(obs_space, dict) and isinstance(obs_space.get("name"), str):
            found.append(node)
        for value in node.values():
            found.extend(collect_observers(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(collect_observers(value))

    return found


def obs_name(observer: dict[str, Any]) -> str:
    obs_space = observer.get("obs space", {})
    if isinstance(obs_space, dict):
        return str(obs_space.get("name", ""))
    return ""


def obsfile(observer: dict[str, Any]) -> str:
    obs_space = observer.get("obs space", {})
    if not isinstance(obs_space, dict):
        return ""
    obsdatain = obs_space.get("obsdatain", {})
    if not isinstance(obsdatain, dict):
        return ""
    engine = obsdatain.get("engine", {})
    if not isinstance(engine, dict):
        return ""
    return str(engine.get("obsfile", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rendered JEDI observer configuration.")
    parser.add_argument(
        "--jedi-yaml",
        type=Path,
        default=Path("build/rendered/3dvar_fgat.yaml"),
    )
    parser.add_argument(
        "--observer-manifest",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/observers.yaml"),
    )
    parser.add_argument(
        "--ioda-inventory",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/ioda_inventory.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail if expected observers are missing.")
    args = parser.parse_args()

    if not args.jedi_yaml.is_file():
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] rendered JEDI YAML not found: {args.jedi_yaml}")
        return 2 if args.strict else 0

    jedi = read_yaml(args.jedi_yaml)
    expected_manifest = observer_manifest_names(args.observer_manifest)
    expected_ioda = ioda_inventory_names(args.ioda_inventory)
    expected = sorted(set(expected_manifest) | set(expected_ioda))

    observers = collect_observers(jedi)
    rendered_names = sorted({obs_name(observer) for observer in observers if obs_name(observer)})

    print(f"[INFO] Rendered JEDI YAML: {args.jedi_yaml}")
    print(f"[INFO] Expected observers: {expected}")
    print(f"[INFO] Rendered observers: {rendered_names}")

    ok = True
    for name in expected:
        if name not in rendered_names:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] expected observer missing from rendered JEDI YAML: {name}")
            if args.strict:
                ok = False

    for name in rendered_names:
        if name not in expected:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] rendered observer not declared in manifest/inventory: {name}")
            if args.strict:
                ok = False

    for observer in observers:
        name = obs_name(observer)
        file_name = obsfile(observer)
        if not file_name:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] observer has no obsdatain.engine.obsfile: {name}")
            if args.strict:
                ok = False
        else:
            print(f"[INFO] observer={name} obsfile={file_name}")

    if not ok:
        return 2

    print("[INFO] Rendered JEDI observer configuration validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
