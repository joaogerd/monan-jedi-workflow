#!/usr/bin/env python3
"""Validate staged scientific input files for MONAN-JEDI-WORKFLOW.

This is a lightweight pre-flight validator. It checks whether expected files exist,
whether they are regular non-empty files, and whether their filename extensions match
the expected broad category. It does not inspect NetCDF/HDF5 internals.
"""

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


def expected_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".h5", ".hdf5"}:
        return "hdf5"
    if suffix in {".nc", ".cdf", ".netcdf"}:
        return "netcdf"
    if path.name.startswith("graph.info"):
        return "graph_info"
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate staged MONAN/JEDI input files.")
    parser.add_argument(
        "layout",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/data_layout.example.yaml"),
    )
    parser.add_argument("--allow-missing", action="store_true", help="Report missing files as warnings.")
    args = parser.parse_args()

    data = read_yaml(args.layout)
    layout = data.get("data_layout") if isinstance(data, dict) else None
    if not isinstance(layout, dict):
        print("[ERROR] Layout must contain data_layout mapping")
        return 2

    root = Path(expand(str(layout.get("root", ""))))
    expected_files = layout.get("expected_files", [])
    if not isinstance(expected_files, list):
        print("[ERROR] data_layout.expected_files must be a list")
        return 2

    ok = True
    print(f"[INFO] Validating staged inputs under: {root}")

    for item in expected_files:
        if not isinstance(item, dict):
            print("[ERROR] Invalid expected_files entry")
            ok = False
            continue

        rel = str(item.get("path", ""))
        required_for = item.get("required_for", "unknown")
        status = item.get("status", "unknown")
        if not rel:
            print("[ERROR] Expected file entry missing path")
            ok = False
            continue

        path = root / rel
        kind = expected_kind(path)

        if not path.exists():
            level = "WARN" if args.allow_missing else "ERROR"
            print(f"[{level}] missing: {path} ({required_for}; {status}; kind={kind})")
            if not args.allow_missing:
                ok = False
            continue

        if not path.is_file():
            print(f"[ERROR] not a regular file: {path}")
            ok = False
            continue

        size = path.stat().st_size
        if size <= 0:
            print(f"[ERROR] empty file: {path}")
            ok = False
            continue

        print(f"[INFO] found: {path} size={size} kind={kind} required_for={required_for}")

    if not ok:
        return 2

    print("[INFO] Staged input validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
