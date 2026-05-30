#!/usr/bin/env python3
"""Check IODA inventory consistency for a MONAN-JEDI experiment.

This utility cross-checks the IODA inventory, the enabled observer manifest, and
the observer plug metadata registry. It verifies that each IODA file entry refers
to an enabled observer, that observer metadata exists, and that the declared IODA
group matches the metadata expectation.

The script can optionally require required IODA files to exist on disk through
``--strict-files``. Without that option, missing files are reported as warnings so
the inventory can be audited before data staging is complete.

Examples
--------
Check the default 3DVar-FGAT IODA inventory::

    $ python tools/check_ioda_inventory.py

Require declared required IODA files to exist::

    $ python tools/check_ioda_inventory.py \
        --inventory configs/experiments/3dvar_fgat/ioda_inventory.yaml \
        --manifest configs/experiments/3dvar_fgat/observers.yaml \
        --metadata configs/jedi/obs_plugs/variational/metadata.yaml \
        --strict-files
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
    This helper intentionally does not enforce a schema. The inventory,
    observer-manifest, and metadata schemas are checked in ``main``.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("inventory.yaml")
    >>> _ = path.write_text("ioda_inventory:\n  files: []\n", encoding="utf-8")
    >>> read_yaml(path)["ioda_inventory"]["files"]
    []
    >>> path.unlink()
    """
    if not path.is_file():
        raise FileNotFoundError(str(path))

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand_path(value: str) -> str:
    """Expand shell-style environment variables in a path string.

    Parameters
    ----------
    value : str
        Path-like text that may contain variables such as ``${MONAN_DATA_ROOT}``.

    Returns
    -------
    str
        Expanded path-like text according to the current process environment.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    Undefined variables remain unchanged and can be detected with
    ``has_unresolved_var``.

    See Also
    --------
    has_unresolved_var : Detect unresolved variable markers.
    os.path.expandvars : Expand environment variables.

    Examples
    --------
    >>> expand_path("/tmp/${UNDEFINED_IODA_ROOT}")
    '/tmp/${UNDEFINED_IODA_ROOT}'
    """
    return os.path.expandvars(value)


def has_unresolved_var(value: str) -> bool:
    """Return whether a path-like string still contains a variable marker.

    Parameters
    ----------
    value : str
        Expanded path-like text to inspect.

    Returns
    -------
    bool
        ``True`` when the text contains ``$``; otherwise ``False``.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    The check is conservative. Any remaining dollar sign is treated as a sign
    that path expansion is incomplete.

    See Also
    --------
    expand_path : Expand variables before unresolved-marker detection.

    Examples
    --------
    >>> has_unresolved_var("${MONAN_DATA_ROOT}/obs.nc4")
    True
    >>> has_unresolved_var("/data/obs.nc4")
    False
    """
    return "$" in value


def main() -> int:
    """Run the IODA inventory consistency checker.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when inventory, observer manifest, and
        metadata are consistent. Returns ``2`` when structural mismatches or
        strict file failures are detected.

    Raises
    ------
    FileNotFoundError
        If one of the selected YAML files does not exist.
    yaml.YAMLError
        If one of the YAML files cannot be parsed.
    OSError
        If filesystem metadata cannot be read.

    Notes
    -----
    Enabled observers are derived from the observer manifest. Every enabled
    observer must appear in the IODA inventory, and every inventory observer must
    be enabled. This prevents the rendered observer list and IODA file inventory
    from drifting apart.

    See Also
    --------
    read_yaml : Load the three YAML metadata files.
    expand_path : Expand declared IODA file paths.
    has_unresolved_var : Detect unresolved IODA path variables.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Check IODA inventory against observer manifest.")
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
        "--metadata",
        type=Path,
        default=Path("configs/jedi/obs_plugs/variational/metadata.yaml"),
    )
    parser.add_argument(
        "--strict-files",
        action="store_true",
        help="Require required IODA files to exist on disk.",
    )
    args = parser.parse_args()

    inventory = read_yaml(args.inventory)
    manifest = read_yaml(args.manifest)
    metadata = read_yaml(args.metadata)

    inv = inventory.get("ioda_inventory") if isinstance(inventory, dict) else None
    observers = manifest.get("observers") if isinstance(manifest, dict) else None
    registry = metadata.get("observer_plugs") if isinstance(metadata, dict) else None

    if not isinstance(inv, dict):
        print("[ERROR] Inventory must contain ioda_inventory mapping")
        return 2
    if not isinstance(observers, list):
        print("[ERROR] Manifest must contain observers list")
        return 2
    if not isinstance(registry, dict):
        print("[ERROR] Metadata must contain observer_plugs mapping")
        return 2

    enabled = {entry["name"] for entry in observers if isinstance(entry, dict) and entry.get("enabled", True)}
    files = inv.get("files")
    if not isinstance(files, list) or not files:
        print("[ERROR] IODA inventory must contain non-empty files list")
        return 2

    seen = set()
    ok = True
    for item in files:
        if not isinstance(item, dict):
            print("[ERROR] Inventory file entry must be a mapping")
            ok = False
            continue

        observer = item.get("observer")
        if observer not in enabled:
            print(f"[ERROR] Inventory observer not enabled in manifest: {observer}")
            ok = False
            continue

        seen.add(observer)
        meta = registry.get(observer)
        if not isinstance(meta, dict):
            print(f"[ERROR] Missing metadata for observer: {observer}")
            ok = False
            continue

        if item.get("expected_group") != meta.get("expected_ioda_group"):
            print(f"[ERROR] expected_group mismatch for observer: {observer}")
            ok = False
            continue

        path = str(item.get("path", ""))
        expanded = expand_path(path)
        required = bool(item.get("required", True))
        if not path:
            print(f"[ERROR] Missing IODA path for observer: {observer}")
            ok = False
            continue

        if has_unresolved_var(expanded):
            print(f"[WARN] IODA path has unresolved variable for {observer}: {path}")
        elif required and args.strict_files and not Path(expanded).is_file():
            print(f"[ERROR] Required IODA file not found for {observer}: {expanded}")
            ok = False
            continue
        elif Path(expanded).is_file():
            print(f"[INFO] IODA file found for {observer}: {expanded}")
        else:
            print(f"[WARN] IODA file not found for {observer}: {expanded}")

        print(f"[INFO] IODA inventory entry validated: {observer}")

    missing = sorted(enabled - seen)
    if missing:
        print(f"[ERROR] Enabled observers missing from IODA inventory: {', '.join(missing)}")
        ok = False

    if not ok:
        return 2

    print("[INFO] IODA inventory check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
