#!/usr/bin/env python3
"""Check MPAS-JEDI build discovery manifest for MONAN-JEDI-WORKFLOW."""

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


def check_file(path_text: str, required: bool, strict: bool, label: str) -> bool:
    expanded = expand(path_text)
    if unresolved(expanded):
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} has unresolved variable: {path_text}")
        return not (required and strict)
    path = Path(expanded)
    if not path.is_file():
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} not found: {path}")
        return not (required and strict)
    if not os.access(path, os.X_OK):
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} is not executable: {path}")
        return not (required and strict)
    print(f"[INFO] {label} found: {path}")
    return True


def check_command(command_text: str, required: bool, strict: bool, label: str) -> bool:
    expanded = expand(command_text)
    if unresolved(expanded):
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} command has unresolved variable: {command_text}")
        return not (required and strict)
    found = shutil.which(expanded)
    if found is None:
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} command not found in PATH: {expanded}")
        return not (required and strict)
    print(f"[INFO] {label} command found: {found}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Check MPAS-JEDI build manifest.")
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("configs/sites/jaci/mpas_jedi_build.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail if required files are missing.")
    args = parser.parse_args()

    data = read_yaml(args.manifest)
    root = data.get("mpas_jedi_build") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        print("[ERROR] Manifest must contain mpas_jedi_build mapping")
        return 2

    ok = True
    build_root = expand(str(root.get("build_root", "")))
    print(f"[INFO] Site: {root.get('site')}")
    print(f"[INFO] Status: {root.get('status')}")
    print(f"[INFO] Build root: {build_root}")

    if unresolved(build_root):
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] build_root has unresolved variable: {root.get('build_root')}")
        ok = ok and not args.strict
    elif not Path(build_root).is_dir():
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] build_root is not a directory: {build_root}")
        ok = ok and not args.strict
    else:
        print(f"[INFO] Build root found: {build_root}")

    for item in root.get("required_executables", []):
        if not isinstance(item, dict):
            print("[ERROR] Invalid required executable entry")
            ok = False
            continue
        ok = check_file(str(item.get("path", "")), True, args.strict, str(item.get("name", "unknown"))) and ok

    for item in root.get("optional_executables", []):
        if not isinstance(item, dict):
            print("[ERROR] Invalid optional executable entry")
            ok = False
            continue
        ok = check_file(str(item.get("path", "")), False, args.strict, str(item.get("name", "unknown"))) and ok

    for item in root.get("expected_commands", []):
        if not isinstance(item, dict):
            print("[ERROR] Invalid command entry")
            ok = False
            continue
        ok = check_command(
            str(item.get("command", "")),
            bool(item.get("required", True)),
            args.strict,
            str(item.get("name", "unknown")),
        ) and ok

    if not ok:
        return 2

    print("[INFO] MPAS-JEDI build check completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
