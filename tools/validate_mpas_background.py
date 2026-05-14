#!/usr/bin/env python3
"""Basic MPAS background validation for MONAN/JEDI 3DVar-FGAT."""

from __future__ import annotations

import argparse
import importlib.util
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


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def background_from_layout(layout: Path, data_root: Path) -> Path | None:
    data = read_yaml(layout)
    root = data.get("data_layout") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        return None
    for item in root.get("expected_files", []):
        if isinstance(item, dict) and item.get("name") == "background_state":
            value = item.get("path", item.get("target", ""))
            if value:
                path = Path(expand(str(value)))
                return path if path.is_absolute() else data_root / path
    return None


def expected_state_variables(render_context: Path) -> list[str]:
    data = read_yaml(render_context)
    jedi = data.get("jedi", {}) if isinstance(data, dict) else {}
    if not isinstance(jedi, dict):
        return []
    values = jedi.get("state_variables", [])
    if isinstance(values, list):
        return [str(value) for value in values]
    return []


def open_netcdf(path: Path) -> tuple[set[str], dict[str, Any]]:
    if has_module("netCDF4"):
        import netCDF4  # type: ignore

        with netCDF4.Dataset(path, "r") as dataset:
            variables = set(dataset.variables.keys())
            attrs = {name: getattr(dataset, name) for name in dataset.ncattrs()}
            attrs["_dimension_count"] = len(dataset.dimensions)
            attrs["_variable_count"] = len(dataset.variables)
        return variables, attrs

    if has_module("xarray"):
        import xarray as xr  # type: ignore

        with xr.open_dataset(path) as dataset:
            variables = set(dataset.variables.keys())
            attrs = dict(dataset.attrs)
            attrs["_dimension_count"] = len(dataset.dims)
            attrs["_variable_count"] = len(dataset.variables)
        return variables, attrs

    return set(), {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate staged MPAS background file.")
    parser.add_argument("--background", type=Path, default=None)
    parser.add_argument("--layout", type=Path, default=Path("configs/experiments/3dvar_fgat/data_layout.example.yaml"))
    parser.add_argument("--render-context", type=Path, default=Path("configs/experiments/3dvar_fgat/render_context.example.yaml"))
    parser.add_argument("--data-root", default=os.environ.get("MONAN_DATA_ROOT", "${MONAN_DATA_ROOT}"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    data_root_text = expand(str(args.data_root))
    if not data_root_text or "$" in data_root_text:
        print(f"[ERROR] data root is missing or unresolved: {args.data_root}")
        return 2
    data_root = Path(data_root_text)

    background = args.background or background_from_layout(args.layout, data_root)
    if background is None:
        print("[ERROR] Could not determine background path from layout")
        return 2
    if not background.is_absolute():
        background = data_root / background

    print(f"[INFO] Background file: {background}")

    if not background.exists():
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] background file not found: {background}")
        return 2 if args.strict else 0
    if not background.is_file():
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] background path is not a file: {background}")
        return 2 if args.strict else 0
    if background.stat().st_size <= 0:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] background file is empty: {background}")
        return 2 if args.strict else 0

    print(f"[INFO] Background file size: {background.stat().st_size} bytes")

    if background.suffix.lower() not in {".nc", ".nc4", ".cdf"}:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] background extension is not NetCDF-like: {background.suffix}")
        if args.strict:
            return 2

    if not (has_module("netCDF4") or has_module("xarray")):
        print("[WARN] No NetCDF parser available; only existence/size/extension checks were performed")
        print("[INFO] MPAS background validation completed")
        return 0

    try:
        variables, attrs = open_netcdf(background)
    except Exception as exc:  # noqa: BLE001
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] could not open background as NetCDF: {exc}")
        return 2 if args.strict else 0

    print(f"[INFO] Background dimension count: {attrs.get('_dimension_count')}")
    print(f"[INFO] Background variable count: {attrs.get('_variable_count')}")

    expected = expected_state_variables(args.render_context)
    missing = [value for value in expected if value not in variables]
    if missing:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] expected JEDI state variables not found in background: {missing}")
        if args.strict:
            return 2
    else:
        print("[INFO] Expected JEDI state variables found in background")

    time_keys = [key for key in attrs if str(key).lower() in {"start_date", "valid_time", "analysis_time", "time"}]
    if time_keys:
        print(f"[INFO] Background temporal attribute keys: {time_keys}")
    else:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] no obvious temporal global attributes found in background")
        if args.strict:
            return 2

    print("[INFO] MPAS background validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
