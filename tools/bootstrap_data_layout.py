#!/usr/bin/env python3
"""Bootstrap the expected MONAN-JEDI-WORKFLOW data directory layout."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap expected data directory layout.")
    parser.add_argument(
        "layout",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/data_layout.example.yaml"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Show actions without creating directories.")
    parser.add_argument("--check-files", action="store_true", help="Fail if expected files are missing.")
    args = parser.parse_args()

    data = read_yaml(args.layout)
    layout = data.get("data_layout") if isinstance(data, dict) else None
    if not isinstance(layout, dict):
        print("[ERROR] Layout must contain data_layout mapping")
        return 2

    root = Path(expand(str(layout.get("root", ""))))
    if not str(root):
        print("[ERROR] data_layout.root is required")
        return 2

    print(f"[INFO] Data root: {root}")

    for item in layout.get("directories", []):
        directory = root / str(item)
        if args.dry_run:
            print(f"[DRY-RUN] mkdir -p {directory}")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] Directory ready: {directory}")

    ok = True
    files = layout.get("expected_files", [])
    if files:
        print("[INFO] Expected files:")
    for item in files:
        rel = str(item.get("path", "")) if isinstance(item, dict) else ""
        if not rel:
            print("[ERROR] Expected file entry missing path")
            ok = False
            continue
        path = root / rel
        required_for = item.get("required_for", "unknown")
        status = item.get("status", "unknown")
        if path.is_file():
            print(f"  [FOUND] {path} ({required_for})")
        else:
            level = "ERROR" if args.check_files else "WARN"
            print(f"  [{level}] missing: {path} ({required_for}; {status})")
            if args.check_files:
                ok = False

    if not ok:
        return 2

    print("[INFO] Data layout bootstrap completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
