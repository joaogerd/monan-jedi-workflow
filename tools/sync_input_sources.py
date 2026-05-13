#!/usr/bin/env python3
"""Synchronize declared input sources into MONAN_EXTERNAL_DATA_ROOT.

This conservative first version never replaces existing targets. It only links
or copies files when the target does not exist.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand(value: str) -> str:
    return os.path.expandvars(value)


def has_unresolved_variable(value: str) -> bool:
    return "$" in value


def sync_one(item: dict[str, Any], external_root: Path, action: str, dry_run: bool) -> bool:
    name = str(item.get("name", "unnamed"))
    required = bool(item.get("required", True))
    source_raw = str(item.get("source_path", ""))
    target_raw = str(item.get("external_target", ""))

    if not target_raw:
        print(f"[ERROR] missing external_target for {name}")
        return False

    if not source_raw:
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source_path is empty for {name}")
        return dry_run or not required

    source_text = expand(source_raw)
    if has_unresolved_variable(source_text):
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source_path has unresolved variable for {name}: {source_raw}")
        return dry_run or not required

    source = Path(source_text)
    target = external_root / target_raw

    if not source.is_file():
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source file not found for {name}: {source}")
        return dry_run or not required

    if target.exists() or target.is_symlink():
        print(f"[INFO] target already exists, keeping {name}: {target}")
        return True

    if dry_run:
        print(f"[DRY-RUN] {action} {source} -> {target}")
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    if action == "copy":
        shutil.copy2(source, target)
        print(f"[INFO] copied {name}: {source} -> {target}")
    elif action == "link":
        target.symlink_to(source)
        print(f"[INFO] linked {name}: {source} -> {target}")
    else:
        print(f"[ERROR] unsupported action: {action}")
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize input source files into external tree.")
    parser.add_argument(
        "registry",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Show actions without changing files.")
    parser.add_argument("--copy", action="store_true", help="Copy instead of linking.")
    args = parser.parse_args()

    data = read_yaml(args.registry)
    root = data.get("input_sources") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        print("[ERROR] registry must contain input_sources mapping")
        return 2

    destinations = root.get("destinations", {})
    external_root_text = str(destinations.get("external_root", os.environ.get("MONAN_EXTERNAL_DATA_ROOT", "")))
    external_root_expanded = expand(external_root_text)
    if not external_root_expanded or has_unresolved_variable(external_root_expanded):
        print(f"[ERROR] external_root is missing or unresolved: {external_root_text}")
        return 2

    external_root = Path(external_root_expanded)
    action = "copy" if args.copy else "link"

    sources = root.get("sources", [])
    if not isinstance(sources, list):
        print("[ERROR] input_sources.sources must be a list")
        return 2

    print(f"[INFO] Registry: {args.registry}")
    print(f"[INFO] External root: {external_root}")
    print(f"[INFO] Action: {action}")
    if args.dry_run:
        print("[WARN] Dry-run mode. No files will be changed.")
    else:
        external_root.mkdir(parents=True, exist_ok=True)

    ok = True
    for item in sources:
        if not isinstance(item, dict):
            print("[ERROR] invalid source entry")
            ok = False
            continue
        ok = sync_one(item, external_root, action, args.dry_run) and ok

    if not ok:
        return 2

    print("[INFO] Input source synchronization completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
