#!/usr/bin/env python3
"""Check the external input root used by MONAN-JEDI input staging.

This utility validates the external data root declared through the environment
variable ``MONAN_EXTERNAL_DATA_ROOT`` and summarizes the parent directories used
by the input-staging manifest. It is intended as an early, lightweight check
before files are copied or linked into the workflow runtime tree.

The script does not stage data and does not modify the filesystem. It only reads
the staging manifest, expands source paths, reports unresolved source variables,
and verifies whether the configured external root exists and is a directory.

Examples
--------
Check the default 3DVar-FGAT staging example::

    $ MONAN_EXTERNAL_DATA_ROOT=/data/monan python tools/check_external_input_root.py

Allow the external root to be missing during documentation or bootstrap work::

    $ python tools/check_external_input_root.py --allow-missing
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    """Read a YAML document from a UTF-8 file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the YAML file to read.

    Returns
    -------
    Any
        Object returned by ``yaml.safe_load``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist or is not a regular file.
    yaml.YAMLError
        If the file cannot be parsed as YAML.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read due to permissions or another filesystem
        problem.

    Notes
    -----
    This helper performs generic YAML loading only. The required
    ``input_staging`` schema is checked by ``main``.

    See Also
    --------
    yaml.safe_load : Safely parse YAML configuration files.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("staging.yaml")
    >>> _ = path.write_text("input_staging:\n  files: []\n", encoding="utf-8")
    >>> read_yaml(path)["input_staging"]["files"]
    []
    >>> path.unlink()
    """
    if not path.is_file():
        raise FileNotFoundError(str(path))

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand(value: str) -> str:
    """Expand environment variables in a path string.

    Parameters
    ----------
    value : str
        Text that may contain shell-style variables, for example
        ``${MONAN_EXTERNAL_DATA_ROOT}``.

    Returns
    -------
    str
        Expanded text using the current process environment.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    Undefined variables remain unchanged after ``os.path.expandvars``. The
    ``unresolved`` helper is used to detect such cases.

    See Also
    --------
    unresolved : Detect unresolved shell-variable markers.
    os.path.expandvars : Expand environment variables in strings.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_ROOT}")
    '/tmp/${UNDEFINED_MONAN_ROOT}'
    """
    return os.path.expandvars(value)


def unresolved(value: str) -> bool:
    """Return whether a string still contains an unresolved variable marker.

    Parameters
    ----------
    value : str
        Expanded text to inspect.

    Returns
    -------
    bool
        ``True`` when ``value`` still contains ``$``; otherwise ``False``.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    The check is deliberately conservative. In this workflow, staging source
    paths should be concrete by the time this diagnostic is run.

    See Also
    --------
    expand : Expand variables before checking unresolved markers.

    Examples
    --------
    >>> unresolved("${MONAN_EXTERNAL_DATA_ROOT}/file.nc")
    True
    >>> unresolved("/data/monan/file.nc")
    False
    """
    return "$" in value


def main() -> int:
    """Run the external input-root diagnostic.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when the external root is valid or when
        ``--allow-missing`` permits a missing root. Returns ``2`` for malformed
        manifests or required root failures.

    Raises
    ------
    FileNotFoundError
        If the selected staging manifest does not exist.
    yaml.YAMLError
        If the staging manifest is not valid YAML.
    OSError
        If the manifest cannot be read or filesystem metadata cannot be checked.

    Notes
    -----
    The source parent directories printed by this command are derived from the
    staging manifest entries. They help users identify which external data
    directories must be mounted or synchronized before the workflow runs.

    See Also
    --------
    read_yaml : Load the staging manifest.
    expand : Expand source paths and the external-root variable.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Check external input root for staging.")
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/staging.example.yaml"),
    )
    parser.add_argument("--allow-missing", action="store_true", help="Report missing root as warning.")
    args = parser.parse_args()

    data = read_yaml(args.manifest)
    staging = data.get("input_staging") if isinstance(data, dict) else None
    if not isinstance(staging, dict):
        print("[ERROR] Manifest must contain input_staging mapping")
        return 2

    files = staging.get("files", [])
    if not isinstance(files, list):
        print("[ERROR] input_staging.files must be a list")
        return 2

    roots = set()
    for item in files:
        if not isinstance(item, dict):
            continue

        source = str(item.get("source", ""))
        expanded = expand(source)
        if unresolved(expanded):
            print(f"[WARN] unresolved source: {source}")
            continue

        # Keep only parent directories because the purpose is to summarize input
        # locations, not to validate every individual source file here.
        path = Path(expanded)
        roots.add(path.parent)

    external_root = expand(os.environ.get("MONAN_EXTERNAL_DATA_ROOT", ""))
    if not external_root:
        level = "WARN" if args.allow_missing else "ERROR"
        print(f"[{level}] MONAN_EXTERNAL_DATA_ROOT is not set")
        return 0 if args.allow_missing else 2

    root_path = Path(external_root)
    if unresolved(external_root):
        level = "WARN" if args.allow_missing else "ERROR"
        print(f"[{level}] MONAN_EXTERNAL_DATA_ROOT is unresolved: {external_root}")
        return 0 if args.allow_missing else 2

    if not root_path.exists():
        level = "WARN" if args.allow_missing else "ERROR"
        print(f"[{level}] external input root not found: {root_path}")
        return 0 if args.allow_missing else 2

    if not root_path.is_dir():
        print(f"[ERROR] external input root is not a directory: {root_path}")
        return 2

    print(f"[INFO] External input root found: {root_path}")
    if roots:
        print("[INFO] Source parent directories from staging manifest:")
        for root in sorted(roots):
            if root.exists():
                print(f"  [FOUND] {root}")
            else:
                print(f"  [WARN] missing: {root}")

    print("[INFO] External input root check completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
