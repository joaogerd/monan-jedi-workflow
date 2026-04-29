#!/usr/bin/env python3
"""Stage external scientific input files into MONAN_DATA_ROOT."""

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


def unresolved(value: str) -> bool:
    return "$" in value


def remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def stage_one(item: dict[str, Any], data_root: Path, default_action: str, dry_run: bool, force: bool) -> bool:
    name = str(item.get("name", "unnamed"))
    source_raw = str(item.get("source", ""))
    target_raw = str(item.get("target", ""))
    required = bool(item.get("required", True))
    action = str(item.get("action", default_action))

    if not source_raw or not target_raw:
        print(f"[ERROR] Invalid staging entry: {name}")
        return False

    source_text = expand(source_raw)
    target = data_root / target_raw

    if unresolved(source_text):
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source has unresolved variable for {name}: {source_raw}")
        return dry_run or not required

    source = Path(source_text)
    if not source.exists():
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source not found for {name}: {source}")
        return dry_run or not required

    if target.exists() or target.is_symlink():
        if force:
            if dry_run:
                print(f"[DRY-RUN] remove existing target: {target}")
            else:
                remove_existing(target)
                print(f"[INFO] Removed existing target: {target}")
        else:
            print(f"[INFO] Target already exists, keeping: {target}")
            return True

    if dry_run:
        print(f"[DRY-RUN] {action} {source} -> {target}")
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    if action == "copy":
        shutil.copy2(source, target)
        print(f"[INFO] Copied {name}: {source} -> {target}")
    elif action == "link":
        target.symlink_to(source)
        print(f"[INFO] Linked {name}: {source} -> {target}")
    else:
        print(f"[ERROR] Unsupported staging action for {name}: {action}")
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage MONAN/JEDI scientific inputs.")
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/staging.example.yaml"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Show staging actions without changing files.")
    parser.add_argument("--copy", action="store_true", help="Override manifest actions and copy files.")
    parser.add_argument("--link", action="store_true", help="Override manifest actions and link files.")
    parser.add_argument("--force", action="store_true", help="Replace existing targets.")
    args = parser.parse_args()

    data = read_yaml(args.manifest)
    staging = data.get("input_staging") if isinstance(data, dict) else None
    if not isinstance(staging, dict):
        print("[ERROR] Manifest must contain input_staging mapping")
        return 2

    data_root = Path(expand(str(staging.get("data_root", ""))))
    default_action = str(staging.get("default_action", "link"))
    if args.copy:
        default_action = "copy"
    if args.link:
        default_action = "link"

    files = staging.get("files", [])
    if not isinstance(files, list):
        print("[ERROR] input_staging.files must be a list")
        return 2

    print(f"[INFO] Data root: {data_root}")
    print(f"[INFO] Default staging action: {default_action}")

    ok = True
    for item in files:
        if not isinstance(item, dict):
            print("[ERROR] Invalid staging item")
            ok = False
            continue
        ok = stage_one(item, data_root, default_action, args.dry_run, args.force) and ok

    if not ok:
        return 2

    print("[INFO] Input staging completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
