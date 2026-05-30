#!/usr/bin/env python3
"""Validate the basic IODA/HDF5 structure used by MONAN-JEDI observers.

This command performs lightweight structural validation of observation files
listed in a MONAN-JEDI IODA inventory. It verifies file existence, file size,
common IODA root groups, and, when possible, the presence of variables expected
by the corresponding observer configuration.

The validator is intentionally limited. It is not a complete IODA, UFO, or
scientific-quality-control validator. Its purpose is to catch early workflow
problems before an expensive 3DVar/FGAT run is submitted on an HPC system, for
example missing files, unresolved data roots, empty NetCDF/HDF5 files, or
observation files that do not expose the expected ``ObsValue`` datasets.

Examples
--------
Validate the default example inventory using ``MONAN_DATA_ROOT``::

    $ python tools/validate_ioda_structure.py

Validate a specific inventory in strict mode::

    $ python tools/validate_ioda_structure.py \
        --inventory configs/experiments/3dvar_fgat/ioda_inventory.yaml \
        --manifest configs/experiments/3dvar_fgat/observers.yaml \
        --data-root /path/to/staged/input/root \
        --strict
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
from typing import Any

import yaml

# Minimal set of groups commonly expected in IODA files consumed by UFO/JEDI.
# The script only checks for their presence. It does not validate dimensions,
# units, channels, coordinates, or scientific values.
COMMON_IODA_GROUPS = ["MetaData", "ObsValue", "ObsError", "PreQC"]


def read_yaml(path: Path) -> Any:
    """Read a YAML document from disk.

    Parameters
    ----------
    path : pathlib.Path
        Path to a YAML file encoded as UTF-8 text.

    Returns
    -------
    Any
        Python object returned by ``yaml.safe_load``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist or is not a regular file.
    yaml.YAMLError
        If the file is not valid YAML.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read due to permissions or another filesystem
        problem.

    Notes
    -----
    The function does not enforce a schema. Schema-specific checks are performed
    by ``manifest_entries`` and ``observer_manifest_by_name``.

    See Also
    --------
    yaml.safe_load : Safely parse YAML content.
    manifest_entries : Read entries from the IODA inventory schema.
    observer_manifest_by_name : Read observer metadata by observer name.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("sample.yaml")
    >>> _ = path.write_text("root:\n  value: 1\n", encoding="utf-8")
    >>> read_yaml(path)["root"]["value"]
    1
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
        Input text that may contain variables such as ``$MONAN_DATA_ROOT`` or
        ``${MONAN_DATA_ROOT}``.

    Returns
    -------
    str
        Expanded string according to the current process environment.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    Undefined environment variables are left unchanged by
    ``os.path.expandvars``. The command-line driver treats a remaining ``$`` in
    the data root as an unresolved configuration error.

    See Also
    --------
    os.path.expandvars : Expand environment variables in path-like strings.

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
        Module name to search for, for example ``"h5py"``.

    Returns
    -------
    bool
        ``True`` when the module can be resolved by the current Python
        interpreter, otherwise ``False``.

    Raises
    ------
    ValueError
        If ``name`` is an invalid module name for import resolution.

    Notes
    -----
    ``h5py`` is optional for this script. When it is unavailable, the validator
    still performs existence and file-size checks so it remains useful on minimal
    login-node environments.

    See Also
    --------
    importlib.util.find_spec : Locate importable Python modules.

    Examples
    --------
    >>> has_module("sys")
    True
    """
    return importlib.util.find_spec(name) is not None


def collect_datasets(group: Any, prefix: str = "") -> list[str]:
    """Collect dataset paths from an HDF5-like group recursively.

    Parameters
    ----------
    group : Any
        HDF5-like group object. The object is expected to expose an ``items``
        method, as ``h5py.File`` and ``h5py.Group`` do.
    prefix : str, optional
        Path prefix accumulated during recursive traversal.

    Returns
    -------
    list of str
        Dataset paths relative to the root group, using ``/`` as separator.

    Raises
    ------
    AttributeError
        If ``group`` does not provide an ``items`` method.
    OSError
        If the underlying HDF5 object cannot be traversed.

    Notes
    -----
    HDF5 groups behave like nested mappings. The traversal treats any object with
    an ``items`` attribute as a group and any object without it as a dataset.

    See Also
    --------
    validate_hdf5_file : Use collected paths to inspect ``ObsValue`` variables.

    Examples
    --------
    >>> collect_datasets({"ObsValue": {"air_temperature": object()}})
    ['ObsValue/air_temperature']
    """
    datasets: list[str] = []

    for key, value in group.items():
        path = f"{prefix}/{key}" if prefix else str(key)

        # h5py groups expose items(); datasets do not. This generic check keeps
        # the helper easy to test with plain dictionaries.
        if hasattr(value, "items"):
            datasets.extend(collect_datasets(value, path))
        else:
            datasets.append(path)

    return datasets


def observer_expected_variables(observer_plug: Path) -> list[str]:
    """Extract simulated variables from an observer plug-in YAML file.

    Parameters
    ----------
    observer_plug : pathlib.Path
        Path to a rendered or source observer YAML fragment. The expected format
        is a list whose first element contains an ``obs space`` mapping.

    Returns
    -------
    list of str
        Names listed under ``obs space.simulated variables``. Returns an empty
        list when the expected structure is absent.

    Raises
    ------
    FileNotFoundError
        If ``observer_plug`` does not exist.
    yaml.YAMLError
        If the observer plug-in file is not valid YAML.
    OSError
        If the file cannot be read.

    Notes
    -----
    Only the first YAML list element is inspected because MONAN-JEDI observer
    plug files are expected to describe one observer block per file in this
    workflow layout.

    See Also
    --------
    read_yaml : Load the observer YAML file.
    validate_hdf5_file : Compare expected variables against ``ObsValue`` groups.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("observer.yaml")
    >>> _ = path.write_text("- obs space:\n    simulated variables: [air_temperature]\n", encoding="utf-8")
    >>> observer_expected_variables(path)
    ['air_temperature']
    >>> path.unlink()
    """
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
    """Read observation entries from an IODA inventory manifest.

    Parameters
    ----------
    manifest_path : pathlib.Path
        Path to the IODA inventory YAML file.

    Returns
    -------
    list of dict
        Observation entries declared under ``ioda_inventory.observations`` or
        ``ioda_inventory.files``. Non-dictionary entries are ignored.

    Raises
    ------
    FileNotFoundError
        If the manifest file does not exist.
    ValueError
        If the manifest does not contain the expected top-level mapping or list.
    yaml.YAMLError
        If the manifest is not valid YAML.

    Notes
    -----
    Both ``observations`` and ``files`` are supported to keep the validator
    compatible with older inventory drafts.

    See Also
    --------
    observer_manifest_by_name : Load observer metadata used to enrich checks.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("ioda_inventory.yaml")
    >>> _ = path.write_text("ioda_inventory:\n  files:\n    - name: aircraft\n      path: aircraft.nc4\n", encoding="utf-8")
    >>> manifest_entries(path)[0]["name"]
    'aircraft'
    >>> path.unlink()
    """
    data = read_yaml(manifest_path)
    root = data.get("ioda_inventory") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        raise ValueError("inventory must contain ioda_inventory mapping")

    entries = root.get("observations", root.get("files", []))
    if not isinstance(entries, list):
        raise ValueError("ioda inventory observations/files must be a list")

    return [entry for entry in entries if isinstance(entry, dict)]


def observer_manifest_by_name(path: Path) -> dict[str, dict[str, Any]]:
    """Index observer manifest entries by observer name.

    Parameters
    ----------
    path : pathlib.Path
        Path to the observer manifest YAML file.

    Returns
    -------
    dict of str to dict
        Mapping from observer name to the corresponding manifest entry.

    Raises
    ------
    FileNotFoundError
        If the observer manifest does not exist.
    ValueError
        If the manifest does not contain an ``observers`` list.
    yaml.YAMLError
        If the manifest is not valid YAML.

    Notes
    -----
    The resulting dictionary is used to connect an IODA inventory entry such as
    ``aircraft`` to the observer plug file that declares its simulated variables.

    See Also
    --------
    observer_expected_variables : Extract variables from an observer plug file.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("observers.yaml")
    >>> _ = path.write_text("observers:\n  - name: aircraft\n    path: aircraft.yaml\n", encoding="utf-8")
    >>> sorted(observer_manifest_by_name(path))
    ['aircraft']
    >>> path.unlink()
    """
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
    """Validate existence and basic IODA/HDF5 structure for one file.

    Parameters
    ----------
    name : str
        Logical observation name used in diagnostic messages.
    path : pathlib.Path
        Absolute or resolved path to the IODA/HDF5 file.
    expected_variables : list of str
        Variables expected under the ``ObsValue`` group. An empty list disables
        this variable-level check.
    strict : bool
        If ``True``, missing files, unreadable files, missing common groups, and
        missing expected variables make the function return ``False``.

    Returns
    -------
    bool
        ``True`` when the file passes the checks or when non-strict mode allows a
        warning. ``False`` when a strict failure is detected.

    Raises
    ------
    OSError
        If filesystem metadata cannot be read for reasons not handled by the
        explicit checks.

    Notes
    -----
    When ``h5py`` is unavailable, the function still checks existence, regular
    file type, and non-zero size. This design keeps the tool usable in restricted
    HPC environments where Python HDF5 bindings may not be loaded by default.

    See Also
    --------
    collect_datasets : Recursively collect HDF5 dataset names.
    has_module : Detect whether ``h5py`` is available.

    Examples
    --------
    >>> validate_hdf5_file("missing", Path("missing.nc4"), [], strict=False)
    [WARN] IODA file missing for missing: missing.nc4
    True
    """
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
        # Dataset paths are collected as ObsValue/variable_name. Splitting once
        # gives the variable names declared inside the ObsValue group.
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
    """Run the IODA structure validation command.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all entries pass under the selected
        policy and ``2`` when metadata parsing fails or a strict validation check
        fails.

    Raises
    ------
    OSError
        If filesystem metadata cannot be accessed for selected files.

    Notes
    -----
    Relative IODA paths from the inventory are resolved against ``--data-root``.
    Absolute IODA paths are used as declared. Observer plug paths are resolved
    against the current working directory when they are relative.

    See Also
    --------
    manifest_entries : Read IODA inventory entries.
    observer_manifest_by_name : Read observer metadata.
    validate_hdf5_file : Validate each resolved observation file.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
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
