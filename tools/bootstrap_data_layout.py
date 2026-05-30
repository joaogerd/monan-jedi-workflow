#!/usr/bin/env python3
"""Bootstrap the expected MONAN-JEDI workflow data directory layout.

This utility reads a data-layout YAML file and creates the directory structure
expected by a MONAN-JEDI experiment. It can also report whether declared input
files are already present under the data root. The tool is useful during the
initial setup of a 3DVar-FGAT experiment, before input files are synchronized,
staged, or validated.

The command is conservative: directory creation is idempotent, and expected files
are only checked, never created. Use ``--dry-run`` to inspect the planned
``mkdir`` operations without changing the filesystem.

Examples
--------
Create the default example data layout::

    $ python tools/bootstrap_data_layout.py

Inspect the directory creation plan only::

    $ python tools/bootstrap_data_layout.py configs/experiments/3dvar_fgat/data_layout.yaml --dry-run

Create directories and fail if expected files are missing::

    $ python tools/bootstrap_data_layout.py configs/experiments/3dvar_fgat/data_layout.yaml --check-files
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
    This helper performs generic YAML loading only. The expected ``data_layout``
    schema is checked by ``main``.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.
    expand : Expand environment variables used in layout paths.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("layout.yaml")
    >>> _ = path.write_text("data_layout:\n  root: data\n", encoding="utf-8")
    >>> read_yaml(path)["data_layout"]["root"]
    'data'
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
    Undefined variables are left unchanged. This keeps unresolved paths visible
    in logs and allows follow-up validators to diagnose the problem.

    See Also
    --------
    os.path.expandvars : Expand environment variables in strings.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_LAYOUT_ROOT}")
    '/tmp/${UNDEFINED_MONAN_LAYOUT_ROOT}'
    """
    return os.path.expandvars(value)


def main() -> int:
    """Run the data-layout bootstrap command.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when directories are created or the
        dry-run succeeds. Returns ``2`` when the layout is invalid or when
        ``--check-files`` detects missing expected files.

    Raises
    ------
    FileNotFoundError
        If the layout YAML file does not exist.
    yaml.YAMLError
        If the layout file is invalid YAML.
    OSError
        If a directory cannot be created or filesystem metadata cannot be read.

    Notes
    -----
    Directory entries are interpreted relative to ``data_layout.root``. Expected
    files are also interpreted relative to that root and are reported as found or
    missing, but the script never creates placeholder data files.

    See Also
    --------
    read_yaml : Load the layout document.
    expand : Expand environment variables in the data root.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Bootstrap expected data directory layout.")
    parser.add_argument(
        "layout",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/data_layout.example.yaml"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Show actions without creating directories.")
    parser.add_argument("--check-files", action="store_true", help="Fail if expected files are missing.")
    args = parser.parse_args()

    data = read_yaml(args.layout)
    layout = data.get("data_layout") if isinstance(data, dict) else None
    if not isinstance(layout, dict):
        print("[ERROR] Layout must contain data_layout mapping")
        return 2

    root = Path(expand(str(layout.get("root", ""))))
    if not str(root):
        print("[ERROR] data_layout.root is required")
        return 2

    print(f"[INFO] Data root: {root}")

    for item in layout.get("directories", []):
        directory = root / str(item)
        if args.dry_run:
            print(f"[DRY-RUN] mkdir -p {directory}")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] Directory ready: {directory}")

    ok = True
    files = layout.get("expected_files", [])
    if files:
        print("[INFO] Expected files:")
    for item in files:
        rel = str(item.get("path", "")) if isinstance(item, dict) else ""
        if not rel:
            print("[ERROR] Expected file entry missing path")
            ok = False
            continue

        path = root / rel
        required_for = item.get("required_for", "unknown")
        status = item.get("status", "unknown")
        if path.is_file():
            print(f"  [FOUND] {path} ({required_for})")
        else:
            level = "ERROR" if args.check_files else "WARN"
            print(f"  [{level}] missing: {path} ({required_for}; {status})")
            if args.check_files:
                ok = False

    if not ok:
        return 2

    print("[INFO] Data layout bootstrap completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
