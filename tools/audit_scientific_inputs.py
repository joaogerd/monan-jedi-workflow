#!/usr/bin/env python3
"""Audit the scientific input checklist for a MONAN-JEDI experiment.

This utility reads the scientific input checklist and reports the declared input
status for each file required by the workflow. It is a provenance-oriented audit:
it summarizes the experiment, cycle, data root, input kind, validation status,
and whether the declared target currently exists on disk.

The script can run in permissive mode, where it only reports the checklist, or in
strict mode, where required inputs must have a validation status compatible with
basic or scientific validation. It does not inspect the scientific contents of the
files; it audits the checklist metadata and file presence.

Examples
--------
Audit the default checklist::

    $ python tools/audit_scientific_inputs.py

Fail if required inputs are not marked as validated::

    $ python tools/audit_scientific_inputs.py configs/experiments/3dvar_fgat/scientific_input_checklist.yaml --strict
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
    The function performs generic YAML loading only. The expected checklist
    structure is validated in ``main``.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("checklist.yaml")
    >>> _ = path.write_text("scientific_input_checklist:\n  inputs: []\n", encoding="utf-8")
    >>> read_yaml(path)["scientific_input_checklist"]["inputs"]
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
    Undefined variables remain unchanged. This keeps unresolved paths visible in
    the audit output instead of hiding configuration problems.

    See Also
    --------
    os.path.expandvars : Expand environment variables in strings.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_DATA_ROOT}")
    '/tmp/${UNDEFINED_MONAN_DATA_ROOT}'
    """
    return os.path.expandvars(value)


def main() -> int:
    """Run the scientific input checklist audit.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when the checklist can be audited and all
        strict checks pass. Returns ``2`` when the checklist structure is invalid
        or a required input is not validated in strict mode.

    Raises
    ------
    FileNotFoundError
        If the checklist file does not exist.
    yaml.YAMLError
        If the checklist file is invalid YAML.
    OSError
        If filesystem metadata cannot be read.

    Notes
    -----
    Strict mode accepts ``validated_basic`` and ``validated_scientific`` as valid
    statuses for required inputs. Other statuses are reported as errors only when
    ``--strict`` is enabled.

    See Also
    --------
    read_yaml : Load the checklist file.
    expand : Expand the declared data root.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Audit scientific input checklist.")
    parser.add_argument(
        "checklist",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/scientific_input_checklist.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail if required inputs are not validated.")
    args = parser.parse_args()

    data = read_yaml(args.checklist)
    checklist = data.get("scientific_input_checklist") if isinstance(data, dict) else None
    if not isinstance(checklist, dict):
        print("[ERROR] Checklist must contain scientific_input_checklist mapping")
        return 2

    data_root = Path(expand(str(checklist.get("data_root", ""))))
    inputs = checklist.get("inputs", [])
    if not isinstance(inputs, list):
        print("[ERROR] scientific_input_checklist.inputs must be a list")
        return 2

    ok = True
    print(f"[INFO] Experiment: {checklist.get('experiment')}")
    print(f"[INFO] Cycle: {checklist.get('cycle')}")
    print(f"[INFO] Data root: {data_root}")

    for item in inputs:
        if not isinstance(item, dict):
            print("[ERROR] Invalid checklist item")
            ok = False
            continue

        name = item.get("name", "unknown")
        target = item.get("target", "")
        required = bool(item.get("required", True))
        status = str(item.get("current_status", "unknown"))
        kind = item.get("kind", "unknown")
        path = data_root / str(target)
        exists = path.is_file()

        print(
            f"[INFO] {name}: required={required} kind={kind} "
            f"status={status} exists={exists} target={target}"
        )

        if required and args.strict and status not in {"validated_basic", "validated_scientific"}:
            print(f"[ERROR] Required input is not validated: {name} status={status}")
            ok = False

    if not ok:
        return 2

    print("[INFO] Scientific input checklist audit completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
