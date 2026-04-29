#!/usr/bin/env python3
"""Check IODA inventory consistency for MONAN-JEDI-WORKFLOW."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand_path(value: str) -> str:
    return os.path.expandvars(value)


def has_unresolved_var(value: str) -> bool:
    return "$" in value


def main() -> int:
    parser = argparse.ArgumentParser(description="Check IODA inventory against observer manifest.")
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/ioda_inventory.example.yaml"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/observers.yaml"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("configs/jedi/obs_plugs/variational/metadata.yaml"),
    )
    parser.add_argument(
        "--strict-files",
        action="store_true",
        help="Require required IODA files to exist on disk.",
    )
    args = parser.parse_args()

    inventory = read_yaml(args.inventory)
    manifest = read_yaml(args.manifest)
    metadata = read_yaml(args.metadata)

    inv = inventory.get("ioda_inventory") if isinstance(inventory, dict) else None
    observers = manifest.get("observers") if isinstance(manifest, dict) else None
    registry = metadata.get("observer_plugs") if isinstance(metadata, dict) else None

    if not isinstance(inv, dict):
        print("[ERROR] Inventory must contain ioda_inventory mapping")
        return 2
    if not isinstance(observers, list):
        print("[ERROR] Manifest must contain observers list")
        return 2
    if not isinstance(registry, dict):
        print("[ERROR] Metadata must contain observer_plugs mapping")
        return 2

    enabled = {entry["name"] for entry in observers if isinstance(entry, dict) and entry.get("enabled", True)}
    files = inv.get("files")
    if not isinstance(files, list) or not files:
        print("[ERROR] IODA inventory must contain non-empty files list")
        return 2

    seen = set()
    ok = True
    for item in files:
        if not isinstance(item, dict):
            print("[ERROR] Inventory file entry must be a mapping")
            ok = False
            continue
        observer = item.get("observer")
        if observer not in enabled:
            print(f"[ERROR] Inventory observer not enabled in manifest: {observer}")
            ok = False
            continue
        seen.add(observer)
        meta = registry.get(observer)
        if not isinstance(meta, dict):
            print(f"[ERROR] Missing metadata for observer: {observer}")
            ok = False
            continue
        if item.get("expected_group") != meta.get("expected_ioda_group"):
            print(f"[ERROR] expected_group mismatch for observer: {observer}")
            ok = False
            continue

        path = str(item.get("path", ""))
        expanded = expand_path(path)
        required = bool(item.get("required", True))
        if not path:
            print(f"[ERROR] Missing IODA path for observer: {observer}")
            ok = False
            continue
        if has_unresolved_var(expanded):
            print(f"[WARN] IODA path has unresolved variable for {observer}: {path}")
        elif required and args.strict_files and not Path(expanded).is_file():
            print(f"[ERROR] Required IODA file not found for {observer}: {expanded}")
            ok = False
            continue
        elif Path(expanded).is_file():
            print(f"[INFO] IODA file found for {observer}: {expanded}")
        else:
            print(f"[WARN] IODA file not found for {observer}: {expanded}")

        print(f"[INFO] IODA inventory entry validated: {observer}")

    missing = sorted(enabled - seen)
    if missing:
        print(f"[ERROR] Enabled observers missing from IODA inventory: {', '.join(missing)}")
        ok = False

    if not ok:
        return 2

    print("[INFO] IODA inventory check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
