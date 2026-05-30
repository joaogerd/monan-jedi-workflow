#!/usr/bin/env python3
"""Stage external scientific input files into ``MONAN_DATA_ROOT``.

This utility reads an input-staging manifest and materializes the files required
by a MONAN-JEDI experiment inside the workflow data root. Each manifest entry
maps an external source file to a target path relative to ``MONAN_DATA_ROOT`` and
can be staged either by symbolic link or by copy.

The tool is intentionally conservative. Existing targets are preserved unless
``--force`` is used, and ``--dry-run`` can be used to inspect the planned actions
without changing the filesystem. This behavior is important in shared HPC
workspaces, where staging should be reproducible and should not silently replace
validated scientific inputs.

Examples
--------
Inspect the default staging plan without changing files::

    $ python tools/stage_inputs.py --dry-run

Create symbolic links declared by the manifest::

    $ python tools/stage_inputs.py configs/experiments/3dvar_fgat/staging.yaml --link

Copy inputs and replace existing targets::

    $ python tools/stage_inputs.py configs/experiments/3dvar_fgat/staging.yaml --copy --force
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
        If the file cannot be read because of permissions or another filesystem
        error.

    Notes
    -----
    The function performs generic loading only. The ``input_staging`` schema is
    validated in ``main`` so error messages can be specific to the command-line
    context.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.
    stage_one : Stage one manifest entry after the YAML has been loaded.

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
    """Expand shell-style environment variables in a string.

    Parameters
    ----------
    value : str
        Text that may contain variables such as ``$MONAN_EXTERNAL_DATA_ROOT`` or
        ``${MONAN_DATA_ROOT}``.

    Returns
    -------
    str
        Expanded value according to the current process environment.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    Undefined variables are left unchanged by ``os.path.expandvars``. The
    ``unresolved`` helper is used after expansion to detect such cases.

    See Also
    --------
    unresolved : Detect values that still contain variable markers.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_INPUT}")
    '/tmp/${UNDEFINED_MONAN_INPUT}'
    """
    return os.path.expandvars(value)


def unresolved(value: str) -> bool:
    """Return whether a string still contains an unresolved variable marker.

    Parameters
    ----------
    value : str
        Expanded path-like string to inspect.

    Returns
    -------
    bool
        ``True`` when ``value`` contains ``$``; otherwise ``False``.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    The check is intentionally simple and conservative. In staging manifests,
    source paths should be concrete before the workflow attempts to copy or link
    files.

    See Also
    --------
    expand : Expand variables before unresolved-marker detection.

    Examples
    --------
    >>> unresolved("${MONAN_ROOT}/file.nc")
    True
    >>> unresolved("/data/monan/file.nc")
    False
    """
    return "$" in value


def remove_existing(path: Path) -> None:
    """Remove an existing file, symlink, or directory target.

    Parameters
    ----------
    path : pathlib.Path
        Existing target path to remove before restaging.

    Returns
    -------
    None
        The function mutates the filesystem and does not return a value.

    Raises
    ------
    FileNotFoundError
        If the path disappears between the caller check and removal.
    OSError
        If the path cannot be removed because of permissions, locks, or another
        filesystem error.

    Notes
    -----
    Symlinks are unlinked directly. Real directories are removed recursively using
    ``shutil.rmtree``. This distinction avoids accidentally following symlinks
    during cleanup.

    See Also
    --------
    shutil.rmtree : Recursively remove directories.
    pathlib.Path.unlink : Remove files and symlinks.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("temporary_target.txt")
    >>> _ = path.write_text("old", encoding="utf-8")
    >>> remove_existing(path)
    >>> path.exists()
    False
    """
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def stage_one(item: dict[str, Any], data_root: Path, default_action: str, dry_run: bool, force: bool) -> bool:
    """Stage one input file declared in the manifest.

    Parameters
    ----------
    item : dict of str to Any
        Manifest entry containing at least ``source`` and ``target``. Optional
        fields include ``name``, ``required``, and ``action``.
    data_root : pathlib.Path
        Root directory where staged targets are created. The manifest target path
        is interpreted relative to this root.
    default_action : str
        Default staging action, usually ``"link"`` or ``"copy"``.
    dry_run : bool
        If ``True``, print the planned action without changing the filesystem.
    force : bool
        If ``True``, remove an existing target before staging the new one.

    Returns
    -------
    bool
        ``True`` when the entry was staged, skipped safely, or accepted under
        dry-run/optional rules. ``False`` when the entry is invalid or a required
        operation cannot be completed.

    Raises
    ------
    OSError
        If filesystem operations such as directory creation, copying, linking, or
        removal fail.

    Notes
    -----
    Required missing sources fail during real staging but are allowed in dry-run
    mode so users can inspect incomplete manifests during setup. Optional missing
    sources are reported as warnings and do not fail the overall command.

    See Also
    --------
    remove_existing : Remove targets when ``force`` is enabled.
    shutil.copy2 : Copy files while preserving metadata.
    pathlib.Path.symlink_to : Create symbolic links.

    Examples
    --------
    >>> item = {"name": "demo", "source": "${MISSING_INPUT}", "target": "demo.nc", "required": False}
    >>> stage_one(item, Path("data"), "link", dry_run=False, force=False)
    [WARN] source has unresolved variable for demo: ${MISSING_INPUT}
    True
    """
    name = str(item.get("name", "unnamed"))
    source_raw = str(item.get("source", ""))
    target_raw = str(item.get("target", ""))
    required = bool(item.get("required", True))
    action = str(item.get("action", default_action))

    if not source_raw or not target_raw:
        print(f"[ERROR] Invalid staging entry: {name}")
        return False

    source_text = expand(source_raw)
    target = data_root / target_raw

    if unresolved(source_text):
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source has unresolved variable for {name}: {source_raw}")
        return dry_run or not required

    source = Path(source_text)
    if not source.exists():
        level = "ERROR" if required and not dry_run else "WARN"
        print(f"[{level}] source not found for {name}: {source}")
        return dry_run or not required

    if target.exists() or target.is_symlink():
        if force:
            if dry_run:
                print(f"[DRY-RUN] remove existing target: {target}")
            else:
                remove_existing(target)
                print(f"[INFO] Removed existing target: {target}")
        else:
            print(f"[INFO] Target already exists, keeping: {target}")
            return True

    if dry_run:
        print(f"[DRY-RUN] {action} {source} -> {target}")
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    if action == "copy":
        shutil.copy2(source, target)
        print(f"[INFO] Copied {name}: {source} -> {target}")
    elif action == "link":
        target.symlink_to(source)
        print(f"[INFO] Linked {name}: {source} -> {target}")
    else:
        print(f"[ERROR] Unsupported staging action for {name}: {action}")
        return False

    return True


def main() -> int:
    """Run the input-staging command-line interface.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all staging entries are valid under
        the selected mode and ``2`` when one or more entries fail.

    Raises
    ------
    FileNotFoundError
        If the staging manifest does not exist.
    yaml.YAMLError
        If the staging manifest is invalid YAML.
    OSError
        If a filesystem operation fails during real staging.

    Notes
    -----
    The manifest must contain an ``input_staging`` mapping. The ``data_root``
    value defines where targets are placed, while each entry under ``files``
    defines a source-to-target staging operation.

    See Also
    --------
    read_yaml : Load the staging manifest.
    stage_one : Stage an individual manifest entry.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Stage MONAN/JEDI scientific inputs.")
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/staging.example.yaml"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Show staging actions without changing files.")
    parser.add_argument("--copy", action="store_true", help="Override manifest actions and copy files.")
    parser.add_argument("--link", action="store_true", help="Override manifest actions and link files.")
    parser.add_argument("--force", action="store_true", help="Replace existing targets.")
    args = parser.parse_args()

    data = read_yaml(args.manifest)
    staging = data.get("input_staging") if isinstance(data, dict) else None
    if not isinstance(staging, dict):
        print("[ERROR] Manifest must contain input_staging mapping")
        return 2

    data_root = Path(expand(str(staging.get("data_root", ""))))
    default_action = str(staging.get("default_action", "link"))
    if args.copy:
        default_action = "copy"
    if args.link:
        default_action = "link"

    files = staging.get("files", [])
    if not isinstance(files, list):
        print("[ERROR] input_staging.files must be a list")
        return 2

    print(f"[INFO] Data root: {data_root}")
    print(f"[INFO] Default staging action: {default_action}")

    ok = True
    for item in files:
        if not isinstance(item, dict):
            print("[ERROR] Invalid staging item")
            ok = False
            continue
        ok = stage_one(item, data_root, default_action, args.dry_run, args.force) and ok

    if not ok:
        return 2

    print("[INFO] Input staging completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
