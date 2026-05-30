#!/usr/bin/env python3
"""Validate the MONAN-JEDI MPAS-JEDI build discovery manifest.

This tool checks whether a site-specific MPAS-JEDI build manifest points to a
usable build tree, required executables, optional executables, and expected shell
commands. It is designed for provenance-oriented workflow validation: before a
3DVar/FGAT experiment is rendered or submitted, the workflow can record whether
the declared binaries and commands are actually visible in the current runtime
environment.

The script supports a permissive default mode and a strict mode. In default mode,
missing paths are reported as warnings whenever possible. In strict mode, missing
or unresolved required entries make the command return a non-zero exit status.

Examples
--------
Validate the default JACI example manifest::

    $ python tools/check_mpas_jedi_build.py

Validate a specific manifest and fail on missing required entries::

    $ python tools/check_mpas_jedi_build.py configs/sites/jaci/mpas_jedi_build.yaml --strict
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
        Path to the YAML file that will be loaded as UTF-8 text.

    Returns
    -------
    Any
        Python object returned by ``yaml.safe_load``. For the expected manifest,
        this is usually a dictionary with a top-level ``mpas_jedi_build`` key.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not point to an existing regular file.
    yaml.YAMLError
        If the file is not valid YAML.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read due to permissions or another filesystem
        issue.

    Notes
    -----
    ``yaml.safe_load`` is used because the manifest is configuration data, not a
    Python object serialization format.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.
    pathlib.Path.read_text : Read file contents as text.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("manifest.yaml")
    >>> _ = path.write_text("mpas_jedi_build:\n  site: test\n", encoding="utf-8")
    >>> read_yaml(path)["mpas_jedi_build"]["site"]
    'test'
    >>> path.unlink()
    """
    if not path.is_file():
        raise FileNotFoundError(str(path))

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand(value: str) -> str:
    """Expand environment variables in a path or command string.

    Parameters
    ----------
    value : str
        String that may contain shell-style environment variables such as
        ``$HOME`` or ``${MONAN_BUILD_ROOT}``.

    Returns
    -------
    str
        String with environment variables expanded according to the current
        process environment.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    Undefined variables are intentionally left unchanged by
    ``os.path.expandvars``. The companion function ``unresolved`` is then used to
    detect those unresolved variables.

    See Also
    --------
    os.path.expandvars : Expand shell-style environment variables.
    unresolved : Detect unresolved variables after expansion.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_TEST_VAR}")
    '/tmp/${UNDEFINED_MONAN_TEST_VAR}'
    """
    return os.path.expandvars(value)


def unresolved(value: str) -> bool:
    """Return whether a string still contains an unresolved variable marker.

    Parameters
    ----------
    value : str
        Expanded path or command text to inspect.

    Returns
    -------
    bool
        ``True`` if the string still contains ``$`` and therefore may include an
        unresolved shell variable, otherwise ``False``.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    The check is deliberately simple. For workflow manifests, any remaining
    dollar sign is considered suspicious because executable paths and command
    names should be concrete by the time the validation step is run.

    See Also
    --------
    expand : Expand environment variables before checking for unresolved values.

    Examples
    --------
    >>> unresolved("/tmp/${MONAN_ROOT}")
    True
    >>> unresolved("/tmp/monan")
    False
    """
    return "$" in value


def check_file(path_text: str, required: bool, strict: bool, label: str) -> bool:
    """Validate that a manifest entry points to an executable file.

    Parameters
    ----------
    path_text : str
        File path read from the manifest. Environment variables are expanded
        before checking the filesystem.
    required : bool
        Whether the file is required for the workflow to proceed.
    strict : bool
        Whether required failures should make the check fail.
    label : str
        Human-readable name used in diagnostic messages.

    Returns
    -------
    bool
        ``True`` when the entry is valid or when the problem is allowed by the
        current ``required`` and ``strict`` settings. ``False`` when the entry is
        invalid and must fail the command.

    Raises
    ------
    TypeError
        If one of the arguments has an incompatible type for path or string
        processing.

    Notes
    -----
    The function checks three conditions in order: unresolved variables,
    existence as a regular file, and executable permission. This ordering keeps
    diagnostics clear and avoids testing permissions on symbolic placeholders.

    See Also
    --------
    check_command : Validate commands that must be found through ``PATH``.
    os.access : Test filesystem permissions.

    Examples
    --------
    >>> check_file("/path/that/does/not/exist", required=False, strict=False, label="optional")
    [WARN] optional not found: /path/that/does/not/exist
    True
    """
    expanded = expand(path_text)
    if unresolved(expanded):
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} has unresolved variable: {path_text}")
        return not (required and strict)

    path = Path(expanded)
    if not path.is_file():
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} not found: {path}")
        return not (required and strict)

    if not os.access(path, os.X_OK):
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} is not executable: {path}")
        return not (required and strict)

    print(f"[INFO] {label} found: {path}")
    return True


def check_command(command_text: str, required: bool, strict: bool, label: str) -> bool:
    """Validate that a command can be resolved through ``PATH``.

    Parameters
    ----------
    command_text : str
        Command name read from the manifest. Environment variables are expanded
        before lookup.
    required : bool
        Whether the command is required for the workflow.
    strict : bool
        Whether required failures should make the validation fail.
    label : str
        Human-readable name used in diagnostic messages.

    Returns
    -------
    bool
        ``True`` when the command is found or when the problem is allowed by the
        current policy. ``False`` when a required command is missing under strict
        validation.

    Raises
    ------
    TypeError
        If one of the arguments has an incompatible type for string processing.

    Notes
    -----
    This function uses ``shutil.which`` and therefore follows the same lookup
    behavior as a shell command search in the current process ``PATH``.

    See Also
    --------
    shutil.which : Locate a command on ``PATH``.
    check_file : Validate explicit executable file paths.

    Examples
    --------
    >>> check_command("python3", required=False, strict=False, label="Python")  # doctest: +ELLIPSIS
    [INFO] Python command found: ...
    True
    """
    expanded = expand(command_text)
    if unresolved(expanded):
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} command has unresolved variable: {command_text}")
        return not (required and strict)

    found = shutil.which(expanded)
    if found is None:
        level = "ERROR" if required and strict else "WARN"
        print(f"[{level}] {label} command not found in PATH: {expanded}")
        return not (required and strict)

    print(f"[INFO] {label} command found: {found}")
    return True


def main() -> int:
    """Run the MPAS-JEDI build manifest validation command.

    Parameters
    ----------
    None
        Command-line arguments are read from ``sys.argv`` by ``argparse``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all checks pass under the selected
        policy and ``2`` when the manifest structure is invalid or a required
        check fails.

    Raises
    ------
    FileNotFoundError
        If the selected manifest does not exist.
    yaml.YAMLError
        If the selected manifest is not valid YAML.
    OSError
        If the manifest cannot be read.

    Notes
    -----
    The manifest is expected to contain a top-level mapping named
    ``mpas_jedi_build``. Within it, the script understands ``build_root``,
    ``required_executables``, ``optional_executables``, and
    ``expected_commands``.

    See Also
    --------
    read_yaml : Read the manifest from disk.
    check_file : Validate executable paths.
    check_command : Validate commands found through ``PATH``.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Check MPAS-JEDI build manifest.")
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("configs/sites/jaci/mpas_jedi_build.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail if required files are missing.")
    args = parser.parse_args()

    data = read_yaml(args.manifest)
    root = data.get("mpas_jedi_build") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        print("[ERROR] Manifest must contain mpas_jedi_build mapping")
        return 2

    ok = True
    build_root = expand(str(root.get("build_root", "")))
    print(f"[INFO] Site: {root.get('site')}")
    print(f"[INFO] Status: {root.get('status')}")
    print(f"[INFO] Build root: {build_root}")

    # Validate the root directory first because all executable paths usually
    # depend on it. Keeping this message early makes HPC logs easier to debug.
    if unresolved(build_root):
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] build_root has unresolved variable: {root.get('build_root')}")
        ok = ok and not args.strict
    elif not Path(build_root).is_dir():
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] build_root is not a directory: {build_root}")
        ok = ok and not args.strict
    else:
        print(f"[INFO] Build root found: {build_root}")

    for item in root.get("required_executables", []):
        if not isinstance(item, dict):
            print("[ERROR] Invalid required executable entry")
            ok = False
            continue

        ok = check_file(str(item.get("path", "")), True, args.strict, str(item.get("name", "unknown"))) and ok

    for item in root.get("optional_executables", []):
        if not isinstance(item, dict):
            print("[ERROR] Invalid optional executable entry")
            ok = False
            continue

        ok = check_file(str(item.get("path", "")), False, args.strict, str(item.get("name", "unknown"))) and ok

    for item in root.get("expected_commands", []):
        if not isinstance(item, dict):
            print("[ERROR] Invalid command entry")
            ok = False
            continue

        ok = check_command(
            str(item.get("command", "")),
            bool(item.get("required", True)),
            args.strict,
            str(item.get("name", "unknown")),
        ) and ok

    if not ok:
        return 2

    print("[INFO] MPAS-JEDI build check completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
