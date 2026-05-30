#!/usr/bin/env python3
"""Validate basic file formats for staged MONAN-JEDI inputs.

This validator performs lightweight format checks for files declared in the
MONAN-JEDI data layout. It verifies file existence, non-empty size, compatibility
between declared kind and filename extension, and optional parser-level opening
for NetCDF and HDF5 files when the required Python libraries are available.

The script does not validate scientific correctness, MPAS mesh compatibility,
IODA schema details, SABER covariance consistency, or observation metadata. It is
intended as a pre-flight diagnostic before expensive JEDI jobs are launched.

Examples
--------
Validate staged files from the default data layout::

    $ python tools/validate_file_formats.py

Fail when required files are missing or invalid::

    $ python tools/validate_file_formats.py configs/experiments/3dvar_fgat/data_layout.yaml --strict
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
from typing import Any

import yaml

# Broad filename-extension expectations for the workflow input kinds. These are
# intentionally simple and should not be interpreted as scientific validation.
EXTENSIONS_BY_KIND = {
    "netcdf": {".nc", ".nc4", ".cdf"},
    "hdf5": {".h5", ".hdf5"},
    "text": {".txt", ".info", ""},
    "graph_info": {".0128", ".info", ""},
}


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
    The function performs generic YAML loading only. Layout schema validation is
    handled by ``main``.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.
    validate_entry : Validate one file entry from the layout.

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
    """Expand shell-style environment variables in a string.

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
    Undefined variables remain unchanged. The command-line driver treats an
    unresolved ``data_root`` as an error.

    See Also
    --------
    os.path.expandvars : Expand environment variables in strings.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_DATA_ROOT}")
    '/tmp/${UNDEFINED_MONAN_DATA_ROOT}'
    """
    return os.path.expandvars(value)


def has_module(name: str) -> bool:
    """Return whether an optional Python module can be imported.

    Parameters
    ----------
    name : str
        Module name to search for, for example ``"netCDF4"`` or ``"h5py"``.

    Returns
    -------
    bool
        ``True`` if the module can be resolved by the current interpreter;
        otherwise ``False``.

    Raises
    ------
    ValueError
        If ``name`` is not a valid module name for import resolution.

    Notes
    -----
    Parser libraries are optional. When they are unavailable, the validator keeps
    running and reports that only existence, size, and extension checks were
    performed.

    See Also
    --------
    importlib.util.find_spec : Locate importable modules.

    Examples
    --------
    >>> has_module("sys")
    True
    """
    return importlib.util.find_spec(name) is not None


def validate_netcdf(path: Path) -> tuple[bool, str]:
    """Try to open a NetCDF file with an available Python parser.

    Parameters
    ----------
    path : pathlib.Path
        NetCDF file path to open.

    Returns
    -------
    tuple of bool and str
        Validation status and a human-readable diagnostic message.

    Raises
    ------
    OSError
        If an available parser cannot open the file.
    ImportError
        If a parser import fails after module discovery.

    Notes
    -----
    ``netCDF4`` is preferred when available. If it is not installed, the function
    tries ``xarray``. If neither parser is available, the function returns success
    with a message explaining that parser-level validation was skipped.

    See Also
    --------
    validate_hdf5 : Parser-level validation for HDF5 files.
    has_module : Detect parser availability.

    Examples
    --------
    >>> isinstance(validate_netcdf, object)
    True
    """
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
    """Try to open an HDF5 file with ``h5py`` when available.

    Parameters
    ----------
    path : pathlib.Path
        HDF5 file path to open.

    Returns
    -------
    tuple of bool and str
        Validation status and a human-readable diagnostic message.

    Raises
    ------
    OSError
        If ``h5py`` is available but cannot open the file.
    ImportError
        If importing ``h5py`` fails after module discovery.

    Notes
    -----
    This function only checks that the file can be opened and reports the number
    of root groups. It does not validate IODA group structure or variable names.

    See Also
    --------
    validate_netcdf : Parser-level validation for NetCDF files.
    has_module : Detect whether ``h5py`` is available.

    Examples
    --------
    >>> isinstance(validate_hdf5, object)
    True
    """
    if has_module("h5py"):
        import h5py  # type: ignore

        with h5py.File(path, "r") as handle:
            keys = list(handle.keys())
        return True, f"opened with h5py; root_groups={len(keys)}"

    return True, "h5py not available; existence/size/extension checks only"


def validate_entry(name: str, target: str, kind: str, required: bool, data_root: Path, strict: bool) -> bool:
    """Validate one expected staged file entry.

    Parameters
    ----------
    name : str
        Logical input name used in diagnostic messages.
    target : str
        Relative path to the expected file under ``data_root``.
    kind : str
        Declared broad file kind, for example ``"netcdf"`` or ``"hdf5"``.
    required : bool
        Whether the file is required for the workflow.
    data_root : pathlib.Path
        Root directory where staged files are expected.
    strict : bool
        If ``True``, missing or invalid required files make validation fail.

    Returns
    -------
    bool
        ``True`` when the entry passes or when non-strict mode allows a warning;
        ``False`` when strict validation fails.

    Raises
    ------
    OSError
        If filesystem metadata cannot be accessed or a parser cannot open an
        existing file.

    Notes
    -----
    The function checks filesystem status before parser-level validation. This
    keeps error messages clear and avoids attempting to open missing or empty
    files.

    See Also
    --------
    validate_netcdf : Open NetCDF files when possible.
    validate_hdf5 : Open HDF5 files when possible.
    EXTENSIONS_BY_KIND : Extension expectations by declared kind.

    Examples
    --------
    >>> validate_entry("missing", "missing.nc", "netcdf", False, Path("data"), strict=False)
    [WARN] missing missing: data/missing.nc
    True
    """
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
    """Run the staged file-format validator.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all entries pass under the selected
        policy and ``2`` when the layout is invalid or strict validation fails.

    Raises
    ------
    FileNotFoundError
        If the layout YAML file does not exist.
    yaml.YAMLError
        If the layout file cannot be parsed.
    OSError
        If filesystem metadata cannot be accessed.

    Notes
    -----
    ``data_root`` is read from ``data_layout.data_root`` when present, otherwise
    from ``MONAN_DATA_ROOT``. Relative expected file paths are resolved under that
    root.

    See Also
    --------
    read_yaml : Load the data layout.
    validate_entry : Validate each expected file entry.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
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
