#!/usr/bin/env python3
"""Validate basic SABER input paths for MONAN-JEDI 3DVar-FGAT.

This utility inspects the render context used by the MONAN-JEDI 3DVar-FGAT
experiment and checks the SABER/BUMP covariance paths declared under the ``jedi``
mapping. It reports the standard-deviation file, NICAS covariance directory, and
vertical-balance covariance directory.

The validation is intentionally lightweight. It checks only whether paths are
resolved and whether they exist on disk. It does not validate SABER covariance
content, BUMP parameter consistency, grid compatibility, or scientific adequacy
for the experiment.

Examples
--------
Validate SABER paths from the default render context::

    $ python tools/validate_saber_inputs.py

Run in strict mode so missing or unresolved paths fail::

    $ python tools/validate_saber_inputs.py \
        --render-context configs/experiments/3dvar_fgat/render_context.yaml \
        --strict
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
        If ``path`` does not exist.
    yaml.YAMLError
        If the file cannot be parsed as YAML.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read.

    Notes
    -----
    The expected ``jedi`` mapping is validated in ``main`` after the YAML file is
    loaded.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.
    expand : Expand environment variables in path values.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("context.yaml")
    >>> _ = path.write_text("jedi:\n  bump_cov_dir: covariance\n", encoding="utf-8")
    >>> read_yaml(path)["jedi"]["bump_cov_dir"]
    'covariance'
    >>> path.unlink()
    """
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand(value: str) -> str:
    """Expand shell-style environment variables in a path string.

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
    Undefined variables remain unchanged and are reported later as unresolved
    paths.

    See Also
    --------
    os.path.expandvars : Expand environment variables in strings.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_SABER_ROOT}")
    '/tmp/${UNDEFINED_SABER_ROOT}'
    """
    return os.path.expandvars(value)


def main() -> int:
    """Run the SABER input path validator.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when the checks complete successfully in
        the selected mode. Returns ``2`` when strict validation detects missing or
        unresolved paths, or when the render context lacks a valid ``jedi``
        mapping.

    Raises
    ------
    FileNotFoundError
        If the render context does not exist.
    yaml.YAMLError
        If the render context is invalid YAML.
    OSError
        If filesystem metadata cannot be read.

    Notes
    -----
    The three keys inspected here are ``bump_cov_stddev_file``, ``bump_cov_dir``,
    and ``bump_cov_vbal_dir``. These names follow the current MONAN-JEDI render
    context convention for SABER/BUMP inputs.

    See Also
    --------
    read_yaml : Load the render context.
    expand : Expand the declared path values.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Validate SABER input paths.")
    parser.add_argument(
        "--render-context",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/render_context.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    data = read_yaml(args.render_context)
    jedi = data.get("jedi", {}) if isinstance(data, dict) else {}
    if not isinstance(jedi, dict):
        print("[ERROR] render context has no jedi mapping")
        return 2

    paths = {
        "stddev_file": expand(str(jedi.get("bump_cov_stddev_file", ""))),
        "nicas_dir": expand(str(jedi.get("bump_cov_dir", ""))),
        "vbal_dir": expand(str(jedi.get("bump_cov_vbal_dir", ""))),
    }

    ok = True
    for label, value in paths.items():
        path = Path(value)
        print(f"[INFO] {label}: {path}")
        if not value or "$" in value:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] unresolved path for {label}: {value}")
            ok = False if args.strict else ok
            continue
        if not path.exists():
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] missing {label}: {path}")
            ok = False if args.strict else ok

    if not ok:
        return 2

    print("[INFO] SABER input validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
