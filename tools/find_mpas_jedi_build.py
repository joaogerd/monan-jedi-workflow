#!/usr/bin/env python3
"""Find candidate MPAS-JEDI build directories on an HPC filesystem.

This utility searches selected filesystem roots for directories that look like
MPAS-JEDI build trees and reports whether they contain executables needed by a
MONAN-JEDI 3DVar workflow. It is designed for HPC environments where users may
have multiple historical build directories and need a reproducible way to select
one for site configuration.

The search is intentionally conservative. It only inspects user-provided roots or
known MONAN/JACI environment roots, walks to a bounded depth, skips large or
irrelevant directories, and checks for executable files under ``bin/``. It does
not build MPAS-JEDI and does not modify any files.

Examples
--------
Search roots discovered from MONAN/JACI environment variables::

    $ python tools/find_mpas_jedi_build.py

Search explicit roots and fail if no 3DVar-capable build is found::

    $ python tools/find_mpas_jedi_build.py /p/projetos/monan_das/joao.gerd/projects --max-depth 4 --strict
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

# Executables required by the current 3DVar/FGAT workflow.
REQUIRED_FOR_3DVAR = ["mpasjedi_variational.x"]

# Common executables that are useful to report even when they are not strictly
# required by the 3DVar validator. They help the user identify whether a build is
# a complete MPAS/JEDI build or only a partial installation.
COMMON_EXECUTABLES = [
    "mpasjedi_variational.x",
    "mpas_atmosphere",
    "mpasjedi_hofx3d.x",
]


def default_roots() -> list[Path]:
    """Build an ordered list of default search roots from environment variables.

    Parameters
    ----------
    None
        Environment variables are read directly from ``os.environ``.

    Returns
    -------
    list of pathlib.Path
        Unique candidate roots inferred from MONAN/JACI-related environment
        variables.

    Raises
    ------
    None
        Missing environment variables are ignored.

    Notes
    -----
    The function preserves discovery order while removing duplicates. This keeps
    the output stable and prioritizes explicit build variables, such as
    ``MPAS_BUNDLE_BUILD``, before broader workspace roots.

    See Also
    --------
    iter_candidate_dirs : Traverse each returned root.

    Examples
    --------
    >>> isinstance(default_roots(), list)
    True
    """
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
    """Yield directories below a root up to a bounded search depth.

    Parameters
    ----------
    root : pathlib.Path
        Root directory to traverse.
    max_depth : int
        Maximum traversal depth relative to ``root``. A value of ``0`` yields
        only ``root`` itself.

    Returns
    -------
    Iterable of pathlib.Path
        Generator-like iterable yielding directory paths that can be inspected as
        possible build candidates.

    Raises
    ------
    RuntimeError
        No explicit runtime errors are raised by design. Directories that cannot
        be listed are skipped.

    Notes
    -----
    The traversal uses an explicit stack rather than recursion. This avoids deep
    Python recursion on large HPC filesystems and makes it easy to prune known
    large directories such as logs, data, scratch, and Spack build stages.

    See Also
    --------
    looks_like_build_dir : Quickly test whether a yielded directory resembles a
        build tree.
    executable_status : Inspect executables inside candidate build directories.

    Examples
    --------
    >>> from pathlib import Path
    >>> root = Path("search_root")
    >>> _ = (root / "build" / "bin").mkdir(parents=True, exist_ok=True)
    >>> any(path.name == "build" for path in iter_candidate_dirs(root, 2))
    True
    >>> import shutil; shutil.rmtree(root)
    """
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
    """Return executable files found in a candidate build directory.

    Parameters
    ----------
    build_dir : pathlib.Path
        Candidate MPAS-JEDI build directory.

    Returns
    -------
    dict of str to pathlib.Path
        Mapping from executable name to its full path for each executable found
        under ``build_dir/bin`` with execute permission.

    Raises
    ------
    OSError
        If filesystem metadata cannot be accessed for a path under ``bin``.

    Notes
    -----
    The function only inspects executable names listed in ``COMMON_EXECUTABLES``.
    It does not scan the entire ``bin`` directory.

    See Also
    --------
    COMMON_EXECUTABLES : Executable names inspected by this function.
    looks_like_build_dir : Pre-filter candidate directories before this check.

    Examples
    --------
    >>> executable_status(Path("definitely_missing_build"))
    {}
    """
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
    """Return whether a directory resembles an MPAS-JEDI build tree.

    Parameters
    ----------
    path : pathlib.Path
        Directory path to inspect.

    Returns
    -------
    bool
        ``True`` when the path is named ``build`` and contains ``bin/``, or when
        it directly contains ``bin/mpasjedi_variational.x``. Otherwise ``False``.

    Raises
    ------
    OSError
        If filesystem metadata cannot be accessed for the inspected path.

    Notes
    -----
    This heuristic keeps the search fast by avoiding expensive executable checks
    for every traversed directory.

    See Also
    --------
    executable_status : Perform detailed executable checks after this filter.

    Examples
    --------
    >>> looks_like_build_dir(Path("definitely_missing_build"))
    False
    """
    if path.name == "build" and (path / "bin").is_dir():
        return True
    if (path / "bin" / "mpasjedi_variational.x").exists():
        return True

    return False


def main() -> int:
    """Run the MPAS-JEDI build finder command.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when the search completes successfully,
        even if no candidates are found in non-strict mode. Returns ``2`` when no
        usable roots or 3DVar-capable builds are found in strict mode.

    Raises
    ------
    OSError
        If filesystem metadata access fails outside the guarded traversal paths.

    Notes
    -----
    When a candidate contains ``mpasjedi_variational.x``, the script prints
    suggested ``site.env`` exports. These values can be copied into the workflow
    environment configuration to make the selected build explicit.

    See Also
    --------
    default_roots : Infer roots from the environment.
    iter_candidate_dirs : Traverse roots safely.
    executable_status : Check candidate executables.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
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
