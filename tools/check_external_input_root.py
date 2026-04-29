#!/usr/bin/env python3
"""Check external input root used by MONAN-JEDI-WORKFLOW staging."""

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


def expand(value: str) -> str:
    return os.path.expandvars(value)


def unresolved(value: str) -> bool:
    return "$" in value


def main() -> int:
    parser = argparse.ArgumentParser(description="Check external input root for staging.")
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/staging.example.yaml"),
    )
    parser.add_argument("--allow-missing", action="store_true", help="Report missing root as warning.")
    args = parser.parse_args()

    data = read_yaml(args.manifest)
    staging = data.get("input_staging") if isinstance(data, dict) else None
    if not isinstance(staging, dict):
        print("[ERROR] Manifest must contain input_staging mapping")
        return 2

    files = staging.get("files", [])
    if not isinstance(files, list):
        print("[ERROR] input_staging.files must be a list")
        return 2

    roots = set()
    for item in files:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", ""))
        expanded = expand(source)
        if unresolved(expanded):
            print(f"[WARN] unresolved source: {source}")
            continue
        path = Path(expanded)
        roots.add(path.parent)

    external_root = expand(os.environ.get("MONAN_EXTERNAL_DATA_ROOT", ""))
    if not external_root:
        level = "WARN" if args.allow_missing else "ERROR"
        print(f"[{level}] MONAN_EXTERNAL_DATA_ROOT is not set")
        return 0 if args.allow_missing else 2

    root_path = Path(external_root)
    if unresolved(external_root):
        level = "WARN" if args.allow_missing else "ERROR"
        print(f"[{level}] MONAN_EXTERNAL_DATA_ROOT is unresolved: {external_root}")
        return 0 if args.allow_missing else 2

    if not root_path.exists():
        level = "WARN" if args.allow_missing else "ERROR"
        print(f"[{level}] external input root not found: {root_path}")
        return 0 if args.allow_missing else 2

    if not root_path.is_dir():
        print(f"[ERROR] external input root is not a directory: {root_path}")
        return 2

    print(f"[INFO] External input root found: {root_path}")
    if roots:
        print("[INFO] Source parent directories from staging manifest:")
        for root in sorted(roots):
            if root.exists():
                print(f"  [FOUND] {root}")
            else:
                print(f"  [WARN] missing: {root}")

    print("[INFO] External input root check completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
