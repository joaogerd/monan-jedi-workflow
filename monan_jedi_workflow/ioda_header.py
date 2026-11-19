"""Inspect IODA NetCDF4/HDF5 structure without an external ncdump binary.

This login-side CLI is a portability fallback for the configured 'ncdump -h'
inspection. It checks actual groups and variables using the required netCDF4
Python dependency; it does not manufacture output markers.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def inspect_header(path: Path) -> list[str]:
    from netCDF4 import Dataset

    names: list[str] = []
    with Dataset(str(path), mode="r") as dataset:
        def visit(group, prefix: str = "") -> None:
            for name in group.dimensions:
                names.append(f"dimension: {prefix}/{name}")
            for name in group.variables:
                names.append(f"variable: {prefix}/{name}")
            for name, child in group.groups.items():
                full = f"{prefix}/{name}"
                names.append(f"group: {full}")
                visit(child, full)
        visit(dataset)
    if not names:
        raise ValueError(f"File contains no NetCDF groups, variables, or dimensions: {path}")
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read real NetCDF/IODA header structure")
    parser.add_argument("file", type=Path)
    options = parser.parse_args(argv)
    try:
        for line in inspect_header(options.file):
            print(line)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"[IODA INSPECTION ERROR] {options.file}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
