#!/usr/bin/env python3
"""Audit the scientific input checklist for MONAN-JEDI-WORKFLOW."""

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
    parser = argparse.ArgumentParser(description="Audit scientific input checklist.")
    parser.add_argument(
        "checklist",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/scientific_input_checklist.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail if required inputs are not validated.")
    args = parser.parse_args()

    data = read_yaml(args.checklist)
    checklist = data.get("scientific_input_checklist") if isinstance(data, dict) else None
    if not isinstance(checklist, dict):
        print("[ERROR] Checklist must contain scientific_input_checklist mapping")
        return 2

    data_root = Path(expand(str(checklist.get("data_root", ""))))
    inputs = checklist.get("inputs", [])
    if not isinstance(inputs, list):
        print("[ERROR] scientific_input_checklist.inputs must be a list")
        return 2

    ok = True
    print(f"[INFO] Experiment: {checklist.get('experiment')}")
    print(f"[INFO] Cycle: {checklist.get('cycle')}")
    print(f"[INFO] Data root: {data_root}")

    for item in inputs:
        if not isinstance(item, dict):
            print("[ERROR] Invalid checklist item")
            ok = False
            continue

        name = item.get("name", "unknown")
        target = item.get("target", "")
        required = bool(item.get("required", True))
        status = str(item.get("current_status", "unknown"))
        kind = item.get("kind", "unknown")
        path = data_root / str(target)
        exists = path.is_file()

        print(
            f"[INFO] {name}: required={required} kind={kind} "
            f"status={status} exists={exists} target={target}"
        )

        if required and args.strict and status not in {"validated_basic", "validated_scientific"}:
            print(f"[ERROR] Required input is not validated: {name} status={status}")
            ok = False

    if not ok:
        return 2

    print("[INFO] Scientific input checklist audit completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
