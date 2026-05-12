#!/usr/bin/env python3
"""Find candidate MPAS-JEDI build directories on an HPC filesystem.

The finder is intentionally conservative: it searches only user-provided roots or
known MONAN/JACI environment roots and looks for expected executables under bin/.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable


REQUIRED_FOR_3DVAR = ["mpasjedi_variational.x"]
COMMON_EXECUTABLES = [
    "mpasjedi_variational.x",
    "mpas_atmosphere",
    "mpasjedi_hofx3d.x",
]


def default_roots() -> list[Path]:
    roots: list[Path] = []
    for name in ["MPAS_BUNDLE_BUILD", "MONAN_WORK_ROOT", "MONAN_WORKFLOW_ROOT", "MONAN_JACI_WORKSPACE"]:
        value = os.environ.get(name)
        if value:
            roots.append(Path(value).expanduser())

    workspace = os.environ.get("MONAN_JACI_WORKSPACE")
    if workspace:
        base = Path(workspace).expanduser()
        roots.extend(
            [
                base / "projects",
                base / "projects" / "jedi",
                base / "projects" / "monan",
                base / "jedi",
                base / "monan",
            ]
        )

    # Preserve order while removing duplicates.
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root)
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def iter_candidate_dirs(root: Path, max_depth: int) -> Iterable[Path]:
    if not root.exists():
        return

    root = root.resolve()
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        if not current.is_dir():
            continue

        yield current

        if depth >= max_depth:
            continue

        try:
            children = list(current.iterdir())
        except OSError:
            continue

        for child in children:
            if not child.is_dir():
                continue
            if child.name in {".git", ".spack", "build_stage", "cache", "logs", "data", "scratch"}:
                continue
            stack.append((child, depth + 1))


def executable_status(build_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    bin_dir = build_dir / "bin"
    if not bin_dir.is_dir():
        return found

    for exe in COMMON_EXECUTABLES:
        path = bin_dir / exe
        if path.is_file() and os.access(path, os.X_OK):
            found[exe] = path
    return found


def looks_like_build_dir(path: Path) -> bool:
    if path.name == "build" and (path / "bin").is_dir():
        return True
    if (path / "bin" / "mpasjedi_variational.x").exists():
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Find candidate MPAS-JEDI build directories.")
    parser.add_argument("roots", nargs="*", type=Path, help="Search roots. Defaults to MONAN/JACI env roots.")
    parser.add_argument("--max-depth", type=int, default=5, help="Maximum directory depth per root.")
    parser.add_argument("--strict", action="store_true", help="Fail if no 3DVar-capable build is found.")
    args = parser.parse_args()

    roots = args.roots or default_roots()
    if not roots:
        print("[WARN] No search roots provided and no MONAN/JACI environment roots found")
        return 2 if args.strict else 0

    print("[INFO] Searching MPAS-JEDI build candidates")
    for root in roots:
        print(f"[INFO] Search root: {root}")

    candidates: list[tuple[Path, dict[str, Path]]] = []
    for root in roots:
        for directory in iter_candidate_dirs(root.expanduser(), args.max_depth):
            if not looks_like_build_dir(directory):
                continue
            found = executable_status(directory)
            if found:
                candidates.append((directory, found))

    if not candidates:
        print("[WARN] No MPAS-JEDI build candidates found")
        return 2 if args.strict else 0

    three_dvar_ready = 0
    for directory, found in candidates:
        has_variational = "mpasjedi_variational.x" in found
        if has_variational:
            three_dvar_ready += 1
        print(f"[INFO] Candidate: {directory}")
        print(f"       3dvar_ready={has_variational}")
        for name in COMMON_EXECUTABLES:
            path = found.get(name)
            status = str(path) if path else "missing"
            print(f"       {name}: {status}")
        if has_variational:
            print("       suggested site.env values:")
            print(f"         export MPAS_BUNDLE_BUILD=\"{directory}\"")
            print(f"         export MPASJEDI_VARIATIONAL_EXE=\"{directory}/bin/mpasjedi_variational.x\"")
            print(f"         export MPAS_ATMOSPHERE_EXE=\"{directory}/bin/mpas_atmosphere\"")
            print(f"         export MPASJEDI_HOFX_EXE=\"{directory}/bin/mpasjedi_hofx3d.x\"")

    if args.strict and three_dvar_ready == 0:
        print("[ERROR] Candidates found, but none contain mpasjedi_variational.x")
        return 2

    print(f"[INFO] MPAS-JEDI build finder completed; candidates={len(candidates)} 3dvar_ready={three_dvar_ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
