#!/usr/bin/env python3
"""Synchronize declared input sources into ``MONAN_EXTERNAL_DATA_ROOT``.

This utility reads the MONAN-JEDI input source registry and creates the external
input tree used later by the staging step. Each registry entry maps a local or
site-specific source file to an ``external_target`` path under the external data
root. Files can be synchronized by symbolic link or by copy.

This first implementation is intentionally conservative: it never replaces an
existing target. If the target already exists, the script reports it and keeps the
current file. This protects manually curated scientific inputs and avoids
silently overwriting shared external datasets.

Examples
--------
Inspect the synchronization plan without changing files::

    $ python tools/sync_input_sources.py --dry-run

Create links under the configured external data root::

    $ python tools/sync_input_sources.py configs/experiments/3dvar_fgat/input_sources.jaci.yaml

Copy files instead of creating symbolic links::

    $ python tools/sync_input_sources.py configs/experiments/3dvar_fgat/input_sources.jaci.yaml --copy
"""

from __future__ import annotations

import argparse
import os
import shutil
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
    Schema validation is performed by ``main`` after loading so the diagnostic
    messages can refer to the expected input-source registry structure.

    See Also
    --------
    yaml.safe_load : Safely parse YAML files.
    sync_one : Synchronize one source entry from the loaded registry.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("sources.yaml")
    >>> _ = path.write_text("input_sources:\n  sources: []\n", encoding="utf-8")
    >>> read_yaml(path)["input_sources"]["sources"]
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
        Text that may contain variables such as ``${MONAN_EXTERNAL_DATA_ROOT}``.

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
    Undefined variables remain unchanged. ``has_unresolved_variable`` is used to
    detect such cases before file operations are attempted.

    See Also
    --------
    has_unresolved_variable : Detect unresolved variable markers.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_SOURCE}")
    '/tmp/${UNDEFINED_MONAN_SOURCE}'
    """
    return os.path.expandvars(value)


def has_unresolved_variable(value: str) -> bool:
    """Return whether a string still contains an unresolved variable marker.

    Parameters
    ----------
    value : str
        Expanded path-like string to inspect.

    Returns
    -------
    bool
        ``True`` when the string contains ``$``; otherwise ``False``.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    The check is conservative because source paths must be concrete before the
    synchronization step can safely create links or copies.

    See Also
    --------
    expand : Expand variables before checking for unresolved markers.

    Examples
    --------
    >>> has_unresolved_variable("${MONAN_ROOT}/file.nc")
    True
    >>> has_unresolved_variable("/data/file.nc")
    False
    """
    return "$" in value


def sync_one(item: dict[str, Any], external_root: Path, action: str, dry_run: bool) -> bool:
    """Synchronize one source file into the external data tree.

    Parameters
    ----------
    item : dict of str to Any
        Input-source registry entry. Expected keys include ``name``,
        ``source_path``, ``external_target``, and optionally ``required``.
    external_root : pathlib.Path
        Root directory where external targets are created.
    action : str
        Synchronization action. Supported values are ``"copy"`` and ``"link"``.
    dry_run : bool
        If ``True``, print the planned operation without changing files.

    Returns
    -------
    bool
        ``True`` when the entry is synchronized, already exists, or is acceptable
        under dry-run/optional rules. ``False`` when a required entry is invalid
        or an unsupported action is requested.

    Raises
    ------
    OSError
        If directory creation, copying, or symlink creation fails during real
        execution.

    Notes
    -----
    Existing targets are never replaced by this tool. This design keeps the
    external data tree stable and avoids accidental overwrites of curated input
    files.

    See Also
    --------
    shutil.copy2 : Copy source files while preserving metadata.
    pathlib.Path.symlink_to : Create symbolic links.

    Examples
    --------
    >>> item = {"name": "optional", "source_path": "${MISSING_SOURCE}", "external_target": "obs.nc", "required": False}
    >>> sync_one(item, Path("external"), "link", dry_run=False)
    [WARN] source_path has unresolved variable for optional: ${MISSING_SOURCE}
    True
    """
    name = str(item.get("name", "unnamed"))
    required = bool(item.get("required", True))
    source_raw = str(item.get("source_path", ""))
    target_raw = str(item.get("external_target", ""))

    if not target_raw:
        print(f"[ERROR] missing external_target for {name}")
        return False

    if not source_raw:
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source_path is empty for {name}")
        return dry_run or not required

    source_text = expand(source_raw)
    if has_unresolved_variable(source_text):
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source_path has unresolved variable for {name}: {source_raw}")
        return dry_run or not required

    source = Path(source_text)
    target = external_root / target_raw

    if not source.is_file():
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source file not found for {name}: {source}")
        return dry_run or not required

    if target.exists() or target.is_symlink():
        print(f"[INFO] target already exists, keeping {name}: {target}")
        return True

    if dry_run:
        print(f"[DRY-RUN] {action} {source} -> {target}")
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    if action == "copy":
        shutil.copy2(source, target)
        print(f"[INFO] copied {name}: {source} -> {target}")
    elif action == "link":
        target.symlink_to(source)
        print(f"[INFO] linked {name}: {source} -> {target}")
    else:
        print(f"[ERROR] unsupported action: {action}")
        return False

    return True


def main() -> int:
    """Run the input-source synchronization command-line interface.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all source entries are synchronized
        or safely skipped. Returns ``2`` when the registry is invalid or at least
        one required entry fails.

    Raises
    ------
    FileNotFoundError
        If the registry file does not exist.
    yaml.YAMLError
        If the registry file is invalid YAML.
    OSError
        If filesystem operations fail during synchronization.

    Notes
    -----
    The external root is read from ``input_sources.destinations.external_root``
    when available. Otherwise, ``MONAN_EXTERNAL_DATA_ROOT`` is used as fallback.

    See Also
    --------
    read_yaml : Load the input-source registry.
    sync_one : Synchronize an individual registry entry.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Synchronize input source files into external tree.")
    parser.add_argument(
        "registry",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Show actions without changing files.")
    parser.add_argument("--copy", action="store_true", help="Copy instead of linking.")
    args = parser.parse_args()

    data = read_yaml(args.registry)
    root = data.get("input_sources") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        print("[ERROR] registry must contain input_sources mapping")
        return 2

    destinations = root.get("destinations", {})
    external_root_text = str(destinations.get("external_root", os.environ.get("MONAN_EXTERNAL_DATA_ROOT", "")))
    external_root_expanded = expand(external_root_text)
    if not external_root_expanded or has_unresolved_variable(external_root_expanded):
        print(f"[ERROR] external_root is missing or unresolved: {external_root_text}")
        return 2

    external_root = Path(external_root_expanded)
    action = "copy" if args.copy else "link"

    sources = root.get("sources", [])
    if not isinstance(sources, list):
        print("[ERROR] input_sources.sources must be a list")
        return 2

    print(f"[INFO] Registry: {args.registry}")
    print(f"[INFO] External root: {external_root}")
    print(f"[INFO] Action: {action}")
    if args.dry_run:
        print("[WARN] Dry-run mode. No files will be changed.")
    else:
        external_root.mkdir(parents=True, exist_ok=True)

    ok = True
    for item in sources:
        if not isinstance(item, dict):
            print("[ERROR] invalid source entry")
            ok = False
            continue
        ok = sync_one(item, external_root, action, args.dry_run) and ok

    if not ok:
        return 2

    print("[INFO] Input source synchronization completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
