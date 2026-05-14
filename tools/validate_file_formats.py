#!/usr/bin/env python3
"""Basic file format validation for staged MONAN/JEDI inputs.

This validator performs lightweight checks only:

- file exists;
- file is not empty;
- declared kind is compatible with file extension;
- NetCDF files can be opened when netCDF4 or xarray is available;
- HDF5 files can be opened when h5py is available.

It does not validate scientific correctness, MPAS mesh compatibility, IODA
schema details or covariance consistency.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
from typing import Any

import yaml


EXTENSIONS_BY_KIND = {
    "netcdf": {".nc", ".nc4", ".cdf"},
    "hdf5": {".h5", ".hdf5"},
    "text": {".txt", ".info", ""},
    "graph_info": {".0128", ".info", ""},
}


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand(value: str) -> str:
    return os.path.expandvars(value)


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def validate_netcdf(path: Path) -> tuple[bool, str]:
    if has_module("netCDF4"):
        import netCDF4  # type: ignore

        with netCDF4.Dataset(path, "r") as dataset:
            dims = len(dataset.dimensions)
            vars_count = len(dataset.variables)
        return True, f"opened with netCDF4; dimensions={dims}; variables={vars_count}"

    if has_module("xarray"):
        import xarray as xr  # type: ignore

        with xr.open_dataset(path) as dataset:
            dims = len(dataset.dims)
            vars_count = len(dataset.data_vars)
        return True, f"opened with xarray; dimensions={dims}; data_vars={vars_count}"

    return True, "netCDF parser not available; existence/size/extension checks only"


def validate_hdf5(path: Path) -> tuple[bool, str]:
    if has_module("h5py"):
        import h5py  # type: ignore

        with h5py.File(path, "r") as handle:
            keys = list(handle.keys())
        return True, f"opened with h5py; root_groups={len(keys)}"

    return True, "h5py not available; existence/size/extension checks only"


def validate_entry(name: str, target: str, kind: str, required: bool, data_root: Path, strict: bool) -> bool:
    path = data_root / target

    if not path.exists():
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] missing {name}: {path}")
        return not (required and strict)

    if not path.is_file():
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] not a regular file {name}: {path}")
        return not (required and strict)

    size = path.stat().st_size
    if size <= 0:
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] empty file {name}: {path}")
        return not (required and strict)

    suffix = path.suffix.lower()
    expected_suffixes = EXTENSIONS_BY_KIND.get(kind, set())
    if expected_suffixes and suffix not in expected_suffixes:
        level = "ERROR" if strict else "WARN"
        print(f"[{level}] extension/kind mismatch for {name}: kind={kind} suffix={suffix}")
        if strict:
            return False

    if kind == "netcdf":
        try:
            ok, message = validate_netcdf(path)
        except Exception as exc:  # noqa: BLE001
            level = "ERROR" if strict else "WARN"
            print(f"[{level}] could not open NetCDF {name}: {path}: {exc}")
            return not strict
        print(f"[INFO] {name}: {message}")
    elif kind == "hdf5":
        try:
            ok, message = validate_hdf5(path)
        except Exception as exc:  # noqa: BLE001
            level = "ERROR" if strict else "WARN"
            print(f"[{level}] could not open HDF5 {name}: {path}: {exc}")
            return not strict
        print(f"[INFO] {name}: {message}")
    else:
        print(f"[INFO] {name}: basic checks passed; kind={kind}; size={size} bytes")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate basic formats of staged input files.")
    parser.add_argument(
        "layout",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/data_layout.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when required files are missing or invalid.")
    args = parser.parse_args()

    data = read_yaml(args.layout)
    root = data.get("data_layout") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        print("[ERROR] layout must contain data_layout mapping")
        return 2

    data_root_text = str(root.get("data_root", os.environ.get("MONAN_DATA_ROOT", "")))
    data_root_expanded = expand(data_root_text)
    if not data_root_expanded or "$" in data_root_expanded:
        print(f"[ERROR] data_root is missing or unresolved: {data_root_text}")
        return 2

    data_root = Path(data_root_expanded)
    expected_files = root.get("expected_files", [])
    if not isinstance(expected_files, list):
        print("[ERROR] data_layout.expected_files must be a list")
        return 2

    print(f"[INFO] Data root: {data_root}")
    if args.strict:
        print("[WARN] Strict mode enabled. Missing/invalid required files will fail.")

    ok = True
    for item in expected_files:
        if not isinstance(item, dict):
            print("[ERROR] invalid expected file entry")
            ok = False
            continue

        name = str(item.get("name", "unnamed"))
        path = str(item.get("path", ""))
        kind = str(item.get("kind", "unknown"))
        required = bool(item.get("required", True))
        ok = validate_entry(name, path, kind, required, data_root, args.strict) and ok

    if not ok:
        return 2

    print("[INFO] Basic file format validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
