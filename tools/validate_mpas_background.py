#!/usr/bin/env python3
"""Validate a staged MPAS background file for MONAN-JEDI 3DVar-FGAT.

This utility performs lightweight validation of the MPAS background/restart file
used by a MONAN-JEDI variational experiment. It checks whether the background
path can be determined, whether the file exists and is non-empty, whether it has
a NetCDF-like extension, and, when a NetCDF parser is available, whether expected
JEDI state variables can be matched to MPAS-native fields.

The validation is intentionally structural. It does not verify full MPAS mesh
compatibility, scientific correctness, interpolation consistency, or SABER
covariance compatibility. Its purpose is to catch common workflow errors before a
costly JEDI job is submitted on an HPC system.

Examples
--------
Validate the background declared in the default data layout::

    $ python tools/validate_mpas_background.py

Validate an explicit background file in strict mode::

    $ python tools/validate_mpas_background.py \
        --background /data/monan/background/mpasout.2018-04-15_00.00.00.nc \
        --render-context configs/experiments/3dvar_fgat/render_context.yaml \
        --data-root /data/monan \
        --strict
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    """Read a YAML document from disk.

    Parameters
    ----------
    path : pathlib.Path
        YAML file path to load as UTF-8 text.

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
    Schema-specific validation is handled by helper functions that know whether
    they are reading a data layout or a render context.

    See Also
    --------
    background_from_layout : Find a background file from a data-layout document.
    expected_state_variables : Read expected JEDI state variables.
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
    Undefined variables remain unchanged and are detected later by the command
    line driver when validating the data root.

    See Also
    --------
    os.path.expandvars : Expand environment variables.
    """
    return os.path.expandvars(value)


def has_module(name: str) -> bool:
    """Return whether an optional Python module can be imported.

    Parameters
    ----------
    name : str
        Module name to search for, for example ``"netCDF4"`` or ``"xarray"``.

    Returns
    -------
    bool
        ``True`` when the module can be resolved by the current interpreter;
        otherwise ``False``.

    Raises
    ------
    ValueError
        If ``name`` is not a valid module name for import resolution.

    Notes
    -----
    NetCDF parsers are optional. If neither ``netCDF4`` nor ``xarray`` is
    available, this script still performs existence, size, and extension checks.

    See Also
    --------
    importlib.util.find_spec : Locate importable modules.
    """
    return importlib.util.find_spec(name) is not None


def looks_like_background(item: dict[str, Any]) -> bool:
    """Return whether a data-layout entry appears to describe an MPAS background.

    Parameters
    ----------
    item : dict of str to Any
        One entry from ``data_layout.expected_files``.

    Returns
    -------
    bool
        ``True`` when the entry matches common background indicators; otherwise
        ``False``.

    Raises
    ------
    None
        Missing keys are treated as empty strings.

    Notes
    -----
    The heuristic supports several workflow conventions: explicit
    ``background_state`` names, entries required for ``3dvar_fgat``, paths under
    ``background/``, and MPAS output filenames containing ``mpasout.``.

    See Also
    --------
    background_from_layout : Use this predicate to select a background path.
    """
    name = str(item.get("name", ""))
    required_for = str(item.get("required_for", ""))
    path = str(item.get("path", item.get("target", "")))
    return (
        name == "background_state"
        or required_for == "3dvar_fgat"
        or path.startswith("background/")
        or "mpasout." in path
    )


def background_from_layout(layout: Path, data_root: Path) -> Path | None:
    """Find the MPAS background path declared in a data-layout file.

    Parameters
    ----------
    layout : pathlib.Path
        Path to a data-layout YAML file.
    data_root : pathlib.Path
        Root directory used to resolve relative background paths.

    Returns
    -------
    pathlib.Path or None
        Absolute or data-root-resolved background path when a matching entry is
        found. Returns ``None`` when no background-like entry is found.

    Raises
    ------
    FileNotFoundError
        If ``layout`` does not exist.
    yaml.YAMLError
        If the layout file cannot be parsed.
    OSError
        If the layout cannot be read.

    Notes
    -----
    Absolute paths are returned unchanged. Relative paths are resolved under
    ``data_root``.

    See Also
    --------
    looks_like_background : Identify candidate layout entries.
    read_yaml : Load the layout file.
    """
    data = read_yaml(layout)
    root = data.get("data_layout") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        return None

    for item in root.get("expected_files", []):
        if not isinstance(item, dict):
            continue
        if looks_like_background(item):
            value = item.get("path", item.get("target", ""))
            if value:
                path = Path(expand(str(value)))
                return path if path.is_absolute() else data_root / path

    return None


def expected_state_variables(render_context: Path) -> list[str]:
    """Read expected JEDI state variables from a render context.

    Parameters
    ----------
    render_context : pathlib.Path
        YAML render context containing a ``jedi`` mapping.

    Returns
    -------
    list of str
        Values from ``jedi.state_variables``. Returns an empty list if the key or
        mapping is absent.

    Raises
    ------
    FileNotFoundError
        If ``render_context`` does not exist.
    yaml.YAMLError
        If the context cannot be parsed.
    OSError
        If the context cannot be read.

    Notes
    -----
    The returned names are JEDI-generic state variable names. They are later
    matched against MPAS-native aliases.

    See Also
    --------
    mpas_native_aliases : Map JEDI names to possible MPAS-native field names.
    """
    data = read_yaml(render_context)
    jedi = data.get("jedi", {}) if isinstance(data, dict) else {}
    if not isinstance(jedi, dict):
        return []

    values = jedi.get("state_variables", [])
    if isinstance(values, list):
        return [str(value) for value in values]

    return []


def mpas_native_aliases(jedi_name: str) -> set[str]:
    """Return MPAS-native fields that can satisfy a JEDI variable name.

    Parameters
    ----------
    jedi_name : str
        Generic JEDI state variable name.

    Returns
    -------
    set of str
        Candidate MPAS-native field names that may satisfy the requested JEDI
        variable. If no explicit mapping exists, the original name is returned.

    Raises
    ------
    None
        Unknown names are handled by returning ``{jedi_name}``.

    Notes
    -----
    MPAS-JEDI YAML commonly uses generic JEDI variable names, while MPAS restart
    and background files store native MPAS variable names. This compact alias
    table follows the same practical idea used by MPAS workflow geovars metadata
    and keeps the validator useful for tutorial data and newer configurations.

    See Also
    --------
    expected_state_variables : Read JEDI variable names from the render context.
    open_netcdf : Read available variable names from the background file.
    """
    aliases = {
        "air_temperature": {"air_temperature", "temperature", "theta", "theta_base"},
        "water_vapor_mixing_ratio_wrt_moist_air": {
            "water_vapor_mixing_ratio_wrt_moist_air",
            "spechum",
            "qv",
        },
        "water_vapor_mixing_ratio_wrt_dry_air": {"water_vapor_mixing_ratio_wrt_dry_air", "qv"},
        "air_pressure_at_surface": {"air_pressure_at_surface", "surface_pressure"},
        "air_pressure": {"air_pressure", "pressure", "pressure_p", "pressure_base"},
        "eastward_wind": {"eastward_wind", "uReconstructZonal", "u10", "u"},
        "northward_wind": {"northward_wind", "uReconstructMeridional", "v10", "u"},
        "air_potential_temperature": {"air_potential_temperature", "theta"},
        "dry_air_density": {"dry_air_density", "rho", "rho_base"},
    }
    return aliases.get(jedi_name, {jedi_name})


def open_netcdf(path: Path) -> tuple[set[str], dict[str, Any]]:
    """Open a NetCDF file and return variable names and global attributes.

    Parameters
    ----------
    path : pathlib.Path
        NetCDF file to open.

    Returns
    -------
    tuple of set and dict
        Set of variable names and dictionary of global attributes. Two synthetic
        attributes, ``_dimension_count`` and ``_variable_count``, are added for
        diagnostics when a parser is available.

    Raises
    ------
    OSError
        If an available parser cannot open the file.
    ImportError
        If parser import fails after discovery.

    Notes
    -----
    ``netCDF4`` is preferred when available. If it is not installed, ``xarray`` is
    used as a fallback. If neither parser is installed, empty structures are
    returned and parser-level checks are skipped by the caller.

    See Also
    --------
    has_module : Detect parser availability.
    mpas_native_aliases : Match expected variables against returned names.
    """
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
    """Run the MPAS background validator.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when validation passes or non-strict mode
        allows warnings. Returns ``2`` when strict validation fails or the
        background path cannot be determined.

    Raises
    ------
    FileNotFoundError
        If selected YAML files do not exist.
    yaml.YAMLError
        If selected YAML files cannot be parsed.
    OSError
        If filesystem metadata or NetCDF parser access fails outside guarded
        checks.

    Notes
    -----
    If ``--background`` is not provided, the script attempts to infer the
    background file from the data layout. Relative background paths are resolved
    under ``--data-root`` or ``MONAN_DATA_ROOT``.

    See Also
    --------
    background_from_layout : Infer background paths from data-layout metadata.
    expected_state_variables : Load expected JEDI variables.
    open_netcdf : Inspect background NetCDF variables and attributes.
    """
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
    missing: list[str] = []
    matched: dict[str, list[str]] = {}

    for value in expected:
        aliases = mpas_native_aliases(value)
        present = sorted(alias for alias in aliases if alias in variables)
        if present:
            matched[value] = present
        else:
            missing.append(value)

    for value, present in matched.items():
        print(f"[INFO] JEDI variable {value} matched MPAS background field(s): {present}")

    if missing:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] expected JEDI state variables not found directly or via MPAS-native aliases: {missing}")
        if args.strict:
            return 2
    else:
        print("[INFO] Expected JEDI state variables matched background fields")

    time_keys = [key for key in attrs if str(key).lower() in {"start_date", "valid_time", "analysis_time", "time"}]
    mpas_time_variables = sorted(name for name in {"xtime", "initial_time", "Time"} if name in variables)

    if time_keys:
        print(f"[INFO] Background temporal attribute keys: {time_keys}")
    elif mpas_time_variables:
        print(f"[INFO] Background MPAS temporal variable(s): {mpas_time_variables}")
    else:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] no obvious temporal global attributes or MPAS temporal variables found in background")
        if args.strict:
            return 2

    print("[INFO] MPAS background validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
