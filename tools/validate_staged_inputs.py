#!/usr/bin/env python3
"""Validate staged scientific input files for MONAN-JEDI workflows.

This script is a lightweight pre-flight validator for files already staged under
the workflow data root. It checks whether expected files exist, whether they are
regular non-empty files, and whether their filename extensions match a broad
category such as NetCDF, HDF5, or MPAS graph metadata.

The validator deliberately does not inspect NetCDF/HDF5 internals. Detailed
scientific and structural checks are handled by more specialized tools. This
script is intended to catch simple but frequent staging problems before a JEDI
application is submitted to an HPC queue.

Examples
--------
Validate the default example data layout::

    $ python tools/validate_staged_inputs.py

Report missing files as warnings while preparing a new dataset::

    $ python tools/validate_staged_inputs.py configs/experiments/3dvar_fgat/data_layout.yaml --allow-missing
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    """Read a YAML document from disk.

    Parameters
    ----------
    path : pathlib.Path
        Path to the YAML file to load as UTF-8 text.

    Returns
    -------
    Any
        Python object returned by ``yaml.safe_load``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist or is not a regular file.
    yaml.YAMLError
        If the file cannot be parsed as YAML.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read.

    Notes
    -----
    This helper does not validate the layout schema. The command-line driver
    checks for the expected ``data_layout`` mapping and ``expected_files`` list.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.
    expected_kind : Infer a broad file kind from a path.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("layout.yaml")
    >>> _ = path.write_text("data_layout:\n  expected_files: []\n", encoding="utf-8")
    >>> read_yaml(path)["data_layout"]["expected_files"]
    []
    >>> path.unlink()
    """
    if not path.is_file():
        raise FileNotFoundError(str(path))

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand(value: str) -> str:
    """Expand shell-style environment variables in a path string.

    Parameters
    ----------
    value : str
        Text that may contain variables such as ``${MONAN_DATA_ROOT}``.

    Returns
    -------
    str
        Expanded text according to the current process environment.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    Undefined variables remain unchanged. This behavior is useful for diagnosing
    incomplete layout files because unresolved values remain visible in printed
    paths.

    See Also
    --------
    os.path.expandvars : Expand environment variables in strings.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_DATA_ROOT}")
    '/tmp/${UNDEFINED_MONAN_DATA_ROOT}'
    """
    return os.path.expandvars(value)


def expected_kind(path: Path) -> str:
    """Infer the broad expected kind of a staged input file.

    Parameters
    ----------
    path : pathlib.Path
        File path whose suffix or name will be inspected.

    Returns
    -------
    str
        Broad file kind. Possible values are ``"hdf5"``, ``"netcdf"``,
        ``"graph_info"``, and ``"unknown"``.

    Raises
    ------
    None
        The function performs string inspection only and does not access the
        filesystem.

    Notes
    -----
    The classification is intentionally broad. Files with ``.h5`` and ``.hdf5``
    suffixes are classified as HDF5, while ``.nc``, ``.cdf``, and ``.netcdf`` are
    classified as NetCDF. MPAS graph files are detected by the ``graph.info``
    filename prefix.

    See Also
    --------
    pathlib.Path.suffix : Return the final path suffix.

    Examples
    --------
    >>> expected_kind(Path("obs.nc"))
    'netcdf'
    >>> expected_kind(Path("graph.info.part.4"))
    'graph_info'
    """
    suffix = path.suffix.lower()
    if suffix in {".h5", ".hdf5"}:
        return "hdf5"
    if suffix in {".nc", ".cdf", ".netcdf"}:
        return "netcdf"
    if path.name.startswith("graph.info"):
        return "graph_info"
    return "unknown"


def main() -> int:
    """Run the staged-input validation command.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all expected files pass validation or
        when missing files are allowed. Returns ``2`` when the layout is invalid
        or required files are missing/invalid.

    Raises
    ------
    FileNotFoundError
        If the layout YAML file does not exist.
    yaml.YAMLError
        If the layout YAML file is invalid.
    OSError
        If filesystem metadata cannot be read.

    Notes
    -----
    The layout root is expanded once and each expected path is interpreted
    relative to that root. Missing files are errors by default, but
    ``--allow-missing`` can be useful during dataset bootstrap.

    See Also
    --------
    read_yaml : Load the data-layout file.
    expected_kind : Classify files for diagnostic output.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
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
