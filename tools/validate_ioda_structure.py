#!/usr/bin/env python3
"""Basic IODA/HDF5 structure validation for MONAN/JEDI observations.

This validator performs lightweight structural checks only. It is not a full
IODA/UFO scientific validator.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
from typing import Any

import yaml


COMMON_IODA_GROUPS = ["MetaData", "ObsValue", "ObsError", "PreQC"]


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand(value: str) -> str:
    return os.path.expandvars(value)


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def collect_datasets(group: Any, prefix: str = "") -> list[str]:
    datasets: list[str] = []
    for key, value in group.items():
        path = f"{prefix}/{key}" if prefix else str(key)
        if hasattr(value, "items"):
            datasets.extend(collect_datasets(value, path))
        else:
            datasets.append(path)
    return datasets


def observer_expected_variables(observer_plug: Path) -> list[str]:
    data = read_yaml(observer_plug)
    if not isinstance(data, list) or not data:
        return []
    first = data[0]
    if not isinstance(first, dict):
        return []
    obs_space = first.get("obs space", {})
    if not isinstance(obs_space, dict):
        return []
    variables = obs_space.get("simulated variables", [])
    if isinstance(variables, list):
        return [str(v) for v in variables]
    return []


def manifest_entries(manifest_path: Path) -> list[dict[str, Any]]:
    data = read_yaml(manifest_path)
    root = data.get("ioda_inventory") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        raise ValueError("inventory must contain ioda_inventory mapping")
    entries = root.get("observations", root.get("files", []))
    if not isinstance(entries, list):
        raise ValueError("ioda inventory observations/files must be a list")
    return [entry for entry in entries if isinstance(entry, dict)]


def observer_manifest_by_name(path: Path) -> dict[str, dict[str, Any]]:
    data = read_yaml(path)
    root = data.get("observers") if isinstance(data, dict) else None
    if not isinstance(root, list):
        raise ValueError("observer manifest must contain observers list")
    result: dict[str, dict[str, Any]] = {}
    for item in root:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            result[name] = item
    return result


def validate_hdf5_file(name: str, path: Path, expected_variables: list[str], strict: bool) -> bool:
    if not path.exists():
        level = "ERROR" if strict else "WARN"
        print(f"[{level}] IODA file missing for {name}: {path}")
        return not strict
    if not path.is_file():
        level = "ERROR" if strict else "WARN"
        print(f"[{level}] IODA path is not a file for {name}: {path}")
        return not strict
    if path.stat().st_size <= 0:
        level = "ERROR" if strict else "WARN"
        print(f"[{level}] IODA file is empty for {name}: {path}")
        return not strict

    if not has_module("h5py"):
        print(f"[WARN] h5py is not available; only existence/size checks were performed for {name}")
        return True

    import h5py  # type: ignore

    try:
        with h5py.File(path, "r") as handle:
            root_keys = sorted(list(handle.keys()))
            datasets = collect_datasets(handle)
    except Exception as exc:  # noqa: BLE001
        level = "ERROR" if strict else "WARN"
        print(f"[{level}] Could not open IODA/HDF5 file for {name}: {path}: {exc}")
        return not strict

    print(f"[INFO] {name}: root groups={root_keys}")
    present_common = [group for group in COMMON_IODA_GROUPS if group in root_keys]
    missing_common = [group for group in COMMON_IODA_GROUPS if group not in root_keys]
    print(f"[INFO] {name}: common IODA groups present={present_common}")
    if missing_common:
        level = "ERROR" if strict else "WARN"
        print(f"[{level}] {name}: common IODA groups missing={missing_common}")
        if strict:
            return False

    if expected_variables:
        obsvalue_names = {dataset.split("/", 1)[1] for dataset in datasets if dataset.startswith("ObsValue/") and "/" in dataset}
        missing_vars = [var for var in expected_variables if var not in obsvalue_names]
        print(f"[INFO] {name}: expected simulated variables={expected_variables}")
        print(f"[INFO] {name}: ObsValue variables found={sorted(obsvalue_names)}")
        if missing_vars:
            level = "ERROR" if strict else "WARN"
            print(f"[{level}] {name}: expected variables not found under ObsValue={missing_vars}")
            if strict:
                return False

    print(f"[INFO] {name}: basic IODA structure check passed")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate basic IODA/HDF5 structure.")
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
        "--data-root",
        default=os.environ.get("MONAN_DATA_ROOT", "${MONAN_DATA_ROOT}"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail when required IODA structure is missing.")
    args = parser.parse_args()

    data_root_text = expand(str(args.data_root))
    if not data_root_text or "$" in data_root_text:
        print(f"[ERROR] data root is missing or unresolved: {args.data_root}")
        return 2
    data_root = Path(data_root_text)

    try:
        inventory = manifest_entries(args.inventory)
        observers = observer_manifest_by_name(args.manifest)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Could not parse IODA metadata: {exc}")
        return 2

    print(f"[INFO] Data root: {data_root}")
    if args.strict:
        print("[WARN] Strict mode enabled. Missing or incomplete IODA files will fail.")

    ok = True
    for entry in inventory:
        name = str(entry.get("name", "unnamed"))
        path_value = entry.get("path", entry.get("target", entry.get("file", "")))
        if not path_value:
            print(f"[ERROR] IODA inventory entry missing path/target/file for {name}")
            ok = False
            continue
        relative_or_absolute = Path(expand(str(path_value)))
        file_path = relative_or_absolute if relative_or_absolute.is_absolute() else data_root / relative_or_absolute

        observer = observers.get(name, {})
        plug_path = observer.get("path", "") if isinstance(observer, dict) else ""
        expected_variables: list[str] = []
        if plug_path:
            plug = Path(str(plug_path))
            if not plug.is_absolute():
                plug = Path.cwd() / plug
            if plug.is_file():
                expected_variables = observer_expected_variables(plug)

        ok = validate_hdf5_file(name, file_path, expected_variables, args.strict) and ok

    if not ok:
        return 2

    print("[INFO] Basic IODA structure validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
