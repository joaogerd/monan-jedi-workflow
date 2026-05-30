#!/usr/bin/env python3
"""Audit the real input source registry for a MONAN-JEDI workflow.

This utility reads the input-source registry and reports the discovery status,
required flag, expanded source path, and filesystem presence for each declared
scientific input. It also reports the MPAS-JEDI build root and variational
executable declared in the registry when that metadata is available.

The audit can be permissive or strict. In permissive mode, it summarizes the
registry without failing on missing files. In strict mode, required source files,
the MPAS-JEDI build root, and the variational executable must exist.

Examples
--------
Audit the default input-source registry::

    $ python tools/audit_input_sources.py

Require all required source files and build paths to exist::

    $ python tools/audit_input_sources.py configs/experiments/3dvar_fgat/input_sources.yaml --strict
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
        YAML file path to read as UTF-8 text.

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
    The function performs generic YAML loading only. The expected
    ``input_sources`` mapping is validated by ``main``.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.
    expand : Expand environment variables in registry paths.

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
        Text that may contain variables such as ``${MONAN_EXTERNAL_DATA_ROOT}``
        or ``${MPAS_BUNDLE_BUILD}``.

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
    Undefined variables remain unchanged. This keeps unresolved registry values
    visible in audit output and avoids silently converting them to empty paths.

    See Also
    --------
    os.path.expandvars : Expand environment variables in strings.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_SOURCE}")
    '/tmp/${UNDEFINED_MONAN_SOURCE}'
    """
    return os.path.expandvars(value)


def main() -> int:
    """Run the input-source registry audit.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when the audit completes and strict checks
        pass. Returns ``2`` when the registry structure is invalid or strict mode
        detects missing required inputs or build artifacts.

    Raises
    ------
    FileNotFoundError
        If the registry file does not exist.
    yaml.YAMLError
        If the registry file is invalid YAML.
    OSError
        If filesystem metadata cannot be read.

    Notes
    -----
    The audit reports ``discovery_status`` exactly as declared in the registry.
    It does not infer scientific validity from the status; strict mode only checks
    whether required source files and declared build artifacts exist on disk.

    See Also
    --------
    read_yaml : Load the registry YAML file.
    expand : Expand source and build paths.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Audit real input source registry.")
    parser.add_argument(
        "registry",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/input_sources.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail if required sources are pending or missing.")
    args = parser.parse_args()

    data = read_yaml(args.registry)
    registry = data.get("input_sources") if isinstance(data, dict) else None
    if not isinstance(registry, dict):
        print("[ERROR] Registry must contain input_sources mapping")
        return 2

    sources = registry.get("sources", [])
    if not isinstance(sources, list):
        print("[ERROR] input_sources.sources must be a list")
        return 2

    print(f"[INFO] Experiment: {registry.get('experiment')}")
    print(f"[INFO] Cycle: {registry.get('cycle')}")
    print(f"[INFO] Registry status: {registry.get('status')}")

    ok = True
    for item in sources:
        if not isinstance(item, dict):
            print("[ERROR] Invalid source entry")
            ok = False
            continue

        name = str(item.get("name", "unknown"))
        required = bool(item.get("required", True))
        status = str(item.get("discovery_status", "unknown"))
        source_path = str(item.get("source_path", ""))
        expanded = expand(source_path) if source_path else ""

        if not source_path:
            print(f"[INFO] {name}: required={required} status={status} source_path=<empty>")
            if required and args.strict:
                print(f"[ERROR] Required source path is empty: {name}")
                ok = False
            continue

        path = Path(expanded)
        exists = path.is_file()
        print(f"[INFO] {name}: required={required} status={status} exists={exists} source_path={expanded}")

        if required and args.strict and not exists:
            print(f"[ERROR] Required source file not found: {name} -> {expanded}")
            ok = False

    build = registry.get("mpas_jedi_build", {})
    if isinstance(build, dict):
        build_root = expand(str(build.get("build_root", "")))
        exe = expand(str(build.get("variational_executable", "")))
        print(f"[INFO] MPAS-JEDI build_root={build_root}")
        print(f"[INFO] MPAS-JEDI variational_executable={exe}")
        if args.strict:
            if not build_root or not Path(build_root).is_dir():
                print(f"[ERROR] MPAS-JEDI build root not found: {build_root}")
                ok = False
            if not exe or not Path(exe).is_file():
                print(f"[ERROR] MPAS-JEDI variational executable not found: {exe}")
                ok = False

    if not ok:
        return 2

    print("[INFO] Input source registry audit completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
