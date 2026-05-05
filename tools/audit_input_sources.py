#!/usr/bin/env python3
"""Audit real input source registry for MONAN-JEDI-WORKFLOW."""

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
    parser = argparse.ArgumentParser(description="Audit real input source registry.")
    parser.add_argument(
        "registry",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/input_sources.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail if required sources are pending or missing.")
    args = parser.parse_args()

    data = read_yaml(args.registry)
    registry = data.get("input_sources") if isinstance(data, dict) else None
    if not isinstance(registry, dict):
        print("[ERROR] Registry must contain input_sources mapping")
        return 2

    sources = registry.get("sources", [])
    if not isinstance(sources, list):
        print("[ERROR] input_sources.sources must be a list")
        return 2

    print(f"[INFO] Experiment: {registry.get('experiment')}")
    print(f"[INFO] Cycle: {registry.get('cycle')}")
    print(f"[INFO] Registry status: {registry.get('status')}")

    ok = True
    for item in sources:
        if not isinstance(item, dict):
            print("[ERROR] Invalid source entry")
            ok = False
            continue

        name = str(item.get("name", "unknown"))
        required = bool(item.get("required", True))
        status = str(item.get("discovery_status", "unknown"))
        source_path = str(item.get("source_path", ""))
        expanded = expand(source_path) if source_path else ""

        if not source_path:
            print(f"[INFO] {name}: required={required} status={status} source_path=<empty>")
            if required and args.strict:
                print(f"[ERROR] Required source path is empty: {name}")
                ok = False
            continue

        path = Path(expanded)
        exists = path.is_file()
        print(f"[INFO] {name}: required={required} status={status} exists={exists} source_path={expanded}")

        if required and args.strict and not exists:
            print(f"[ERROR] Required source file not found: {name} -> {expanded}")
            ok = False

    build = registry.get("mpas_jedi_build", {})
    if isinstance(build, dict):
        build_root = expand(str(build.get("build_root", "")))
        exe = expand(str(build.get("variational_executable", "")))
        print(f"[INFO] MPAS-JEDI build_root={build_root}")
        print(f"[INFO] MPAS-JEDI variational_executable={exe}")
        if args.strict:
            if not build_root or not Path(build_root).is_dir():
                print(f"[ERROR] MPAS-JEDI build root not found: {build_root}")
                ok = False
            if not exe or not Path(exe).is_file():
                print(f"[ERROR] MPAS-JEDI variational executable not found: {exe}")
                ok = False

    if not ok:
        return 2

    print("[INFO] Input source registry audit completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
