#!/usr/bin/env python3
"""Validate rendered JEDI observer configuration against experiment metadata.

This structural validator checks whether the rendered JEDI YAML contains the
observers expected by the experiment observer manifest and the IODA inventory. It
also reports the ``obsdatain.engine.obsfile`` value for each rendered observer so
users can verify that the rendered YAML points to the intended observation files.

The script does not validate complete UFO/JEDI schema correctness and does not
open IODA files. Its role is to detect workflow integration problems such as
missing rendered observers, unexpected observer blocks, or observer blocks without
an ``obsfile`` declaration.

Examples
--------
Validate the default rendered 3DVar-FGAT observer configuration::

    $ python tools/validate_jedi_observer_config.py

Fail when rendered observers differ from the manifest or inventory::

    $ python tools/validate_jedi_observer_config.py \
        --jedi-yaml build/rendered/3dvar_fgat.yaml \
        --observer-manifest configs/experiments/3dvar_fgat/observers.yaml \
        --ioda-inventory configs/experiments/3dvar_fgat/ioda_inventory.yaml \
        --strict
"""

from __future__ import annotations

import argparse
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
    This helper performs generic YAML loading. The expected structures are
    checked by specialized helper functions and by ``main``.

    See Also
    --------
    observer_manifest_names : Extract observer names from the manifest.
    ioda_inventory_names : Extract observer names from the IODA inventory.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("observers.yaml")
    >>> _ = path.write_text("observers: []\n", encoding="utf-8")
    >>> read_yaml(path)["observers"]
    []
    >>> path.unlink()
    """
    if not path.is_file():
        raise FileNotFoundError(str(path))

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def observer_manifest_names(path: Path) -> list[str]:
    """Return observer names declared in an observer manifest.

    Parameters
    ----------
    path : pathlib.Path
        Path to a YAML manifest containing a top-level ``observers`` list.

    Returns
    -------
    list of str
        Observer names found in the manifest.

    Raises
    ------
    FileNotFoundError
        If the manifest does not exist.
    ValueError
        If the manifest does not contain an ``observers`` list.
    yaml.YAMLError
        If the manifest is invalid YAML.

    Notes
    -----
    Entries without a string ``name`` are ignored here. Separate manifest
    validators can enforce stricter entry-level schema requirements.

    See Also
    --------
    ioda_inventory_names : Extract observer names from the IODA inventory.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("manifest.yaml")
    >>> _ = path.write_text("observers:\n  - name: aircraft\n", encoding="utf-8")
    >>> observer_manifest_names(path)
    ['aircraft']
    >>> path.unlink()
    """
    data = read_yaml(path)
    root = data.get("observers") if isinstance(data, dict) else None
    if not isinstance(root, list):
        raise ValueError("observer manifest must contain observers list")

    names: list[str] = []
    for item in root:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(str(item["name"]))

    return names


def ioda_inventory_names(path: Path) -> list[str]:
    """Return observer names declared in an IODA inventory.

    Parameters
    ----------
    path : pathlib.Path
        Path to an IODA inventory YAML file.

    Returns
    -------
    list of str
        Observer names found under ``ioda_inventory.observations`` or
        ``ioda_inventory.files``.

    Raises
    ------
    FileNotFoundError
        If the inventory does not exist.
    ValueError
        If the inventory does not contain the expected mapping/list structure.
    yaml.YAMLError
        If the inventory is invalid YAML.

    Notes
    -----
    The function accepts both ``observations`` and ``files`` to support older and
    newer inventory schemas used by the workflow.

    See Also
    --------
    observer_manifest_names : Extract observer names from the experiment manifest.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("ioda.yaml")
    >>> _ = path.write_text("ioda_inventory:\n  files:\n    - name: aircraft\n", encoding="utf-8")
    >>> ioda_inventory_names(path)
    ['aircraft']
    >>> path.unlink()
    """
    data = read_yaml(path)
    root = data.get("ioda_inventory") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        raise ValueError("IODA inventory must contain ioda_inventory mapping")

    entries = root.get("observations", root.get("files", []))
    if not isinstance(entries, list):
        raise ValueError("IODA inventory observations/files must be a list")

    names: list[str] = []
    for item in entries:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(str(item["name"]))

    return names


def collect_observers(node: Any) -> list[dict[str, Any]]:
    """Find observer dictionaries in a rendered JEDI YAML tree.

    Parameters
    ----------
    node : Any
        YAML-derived object to inspect recursively.

    Returns
    -------
    list of dict
        Observer dictionaries that contain an ``obs space`` mapping with a string
        ``name`` field.

    Raises
    ------
    None
        Unsupported node types are ignored.

    Notes
    -----
    Rendered JEDI YAML can contain observer blocks nested inside different
    application structures. Recursive discovery avoids hard-coding one exact
    path to the observers list.

    See Also
    --------
    obs_name : Extract the observer name from a discovered observer block.
    obsfile : Extract the observation file path from a discovered observer block.

    Examples
    --------
    >>> collect_observers({"obs space": {"name": "aircraft"}})[0]["obs space"]["name"]
    'aircraft'
    """
    found: list[dict[str, Any]] = []

    if isinstance(node, dict):
        obs_space = node.get("obs space")
        if isinstance(obs_space, dict) and isinstance(obs_space.get("name"), str):
            found.append(node)
        for value in node.values():
            found.extend(collect_observers(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(collect_observers(value))

    return found


def obs_name(observer: dict[str, Any]) -> str:
    """Return the ``obs space.name`` value from an observer block.

    Parameters
    ----------
    observer : dict of str to Any
        Rendered observer block.

    Returns
    -------
    str
        Observer name, or an empty string when it cannot be found.

    Raises
    ------
    None
        Missing or malformed fields return an empty string.

    Notes
    -----
    Returning an empty string keeps the caller simple and avoids exceptions while
    scanning partially rendered YAML during development.

    See Also
    --------
    obsfile : Extract the ``obsfile`` path from the same observer block.

    Examples
    --------
    >>> obs_name({"obs space": {"name": "sondes"}})
    'sondes'
    """
    obs_space = observer.get("obs space", {})
    if isinstance(obs_space, dict):
        return str(obs_space.get("name", ""))
    return ""


def obsfile(observer: dict[str, Any]) -> str:
    """Return the ``obsdatain.engine.obsfile`` value from an observer block.

    Parameters
    ----------
    observer : dict of str to Any
        Rendered observer block.

    Returns
    -------
    str
        Observation file path declared by the rendered observer, or an empty
        string when the nested field is missing.

    Raises
    ------
    None
        Missing or malformed nested mappings return an empty string.

    Notes
    -----
    This helper follows the common JEDI/UFO path ``obs space -> obsdatain ->
    engine -> obsfile`` used by IODA-backed observers.

    See Also
    --------
    obs_name : Extract the observer name from the same block.

    Examples
    --------
    >>> block = {"obs space": {"obsdatain": {"engine": {"obsfile": "obs.nc4"}}}}
    >>> obsfile(block)
    'obs.nc4'
    """
    obs_space = observer.get("obs space", {})
    if not isinstance(obs_space, dict):
        return ""
    obsdatain = obs_space.get("obsdatain", {})
    if not isinstance(obsdatain, dict):
        return ""
    engine = obsdatain.get("engine", {})
    if not isinstance(engine, dict):
        return ""
    return str(engine.get("obsfile", ""))


def main() -> int:
    """Run the rendered JEDI observer configuration validator.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when rendered observers are consistent
        with expectations, or when non-strict mode allows warnings. Returns ``2``
        for strict validation failures.

    Raises
    ------
    FileNotFoundError
        If manifest or inventory files are missing.
    yaml.YAMLError
        If a YAML file cannot be parsed.
    OSError
        If files cannot be read.

    Notes
    -----
    Expected observers are the union of names found in the observer manifest and
    IODA inventory. This ensures that the rendered YAML remains consistent with
    both the selected observer plugs and the declared observation files.

    See Also
    --------
    collect_observers : Discover observer blocks in rendered YAML.
    observer_manifest_names : Read expected names from the manifest.
    ioda_inventory_names : Read expected names from the inventory.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Validate rendered JEDI observer configuration.")
    parser.add_argument(
        "--jedi-yaml",
        type=Path,
        default=Path("build/rendered/3dvar_fgat.yaml"),
    )
    parser.add_argument(
        "--observer-manifest",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/observers.yaml"),
    )
    parser.add_argument(
        "--ioda-inventory",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/ioda_inventory.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail if expected observers are missing.")
    args = parser.parse_args()

    if not args.jedi_yaml.is_file():
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] rendered JEDI YAML not found: {args.jedi_yaml}")
        return 2 if args.strict else 0

    jedi = read_yaml(args.jedi_yaml)
    expected_manifest = observer_manifest_names(args.observer_manifest)
    expected_ioda = ioda_inventory_names(args.ioda_inventory)
    expected = sorted(set(expected_manifest) | set(expected_ioda))

    observers = collect_observers(jedi)
    rendered_names = sorted({obs_name(observer) for observer in observers if obs_name(observer)})

    print(f"[INFO] Rendered JEDI YAML: {args.jedi_yaml}")
    print(f"[INFO] Expected observers: {expected}")
    print(f"[INFO] Rendered observers: {rendered_names}")

    ok = True
    for name in expected:
        if name not in rendered_names:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] expected observer missing from rendered JEDI YAML: {name}")
            if args.strict:
                ok = False

    for name in rendered_names:
        if name not in expected:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] rendered observer not declared in manifest/inventory: {name}")
            if args.strict:
                ok = False

    for observer in observers:
        name = obs_name(observer)
        file_name = obsfile(observer)
        if not file_name:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] observer has no obsdatain.engine.obsfile: {name}")
            if args.strict:
                ok = False
        else:
            print(f"[INFO] observer={name} obsfile={file_name}")

    if not ok:
        return 2

    print("[INFO] Rendered JEDI observer configuration validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
