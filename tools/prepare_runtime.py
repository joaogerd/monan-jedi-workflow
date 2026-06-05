#!/usr/bin/env python3
"""Prepare a MONAN-JEDI workflow runtime directory.

This utility creates the directory layout and file links required by a rendered
MONAN-JEDI 3DVar-FGAT experiment. It is deliberately separated from the actual
JEDI execution step so the runtime tree can be inspected and validated before an
expensive HPC job is launched.

The runtime manifest defines a working directory, subdirectories, link/copy
actions, and rendered products. By default, file actions are symbolic links to
avoid duplicating large scientific datasets. The ``--copy`` option can be used
when a self-contained runtime directory is needed.

Examples
--------
Prepare a runtime directory using symlinks::

    $ python tools/prepare_runtime.py build/rendered/runtime.yaml

Inspect planned actions without changing files::

    $ python tools/prepare_runtime.py build/rendered/runtime.yaml --dry-run
"""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LinkAction:
    """Describe one file link or copy operation from the runtime manifest.

    Parameters
    ----------
    name : str
        Human-readable action name used in diagnostic messages.
    source : pathlib.Path
        Source file that should be linked or copied.
    target : pathlib.Path
        Destination path inside the runtime directory.
    required : bool
        Whether a missing source should fail real runtime preparation.

    Returns
    -------
    LinkAction
        Immutable dataclass instance containing one planned runtime action.

    Raises
    ------
    TypeError
        If incompatible values are provided and later used as paths or booleans.

    Notes
    -----
    The dataclass is frozen so planned actions are not accidentally changed after
    they are built from the manifest.

    See Also
    --------
    build_actions : Build ``LinkAction`` objects from a manifest.
    apply_action : Execute or simulate one action.

    Examples
    --------
    >>> action = LinkAction("yaml", Path("source.yaml"), Path("work/source.yaml"), True)
    >>> action.name
    'yaml'
    """

    name: str
    source: Path
    target: Path
    required: bool


def expand_value(value: str) -> str:
    """Expand environment variables in a string value.

    Parameters
    ----------
    value : str
        Text that may contain shell-style variables such as ``$MONAN_DATA_ROOT``.

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
    Undefined variables remain unchanged after expansion, allowing later
    validators to report unresolved values explicitly.

    See Also
    --------
    os.path.expandvars : Expand environment variables in strings.

    Examples
    --------
    >>> expand_value("/tmp/${UNDEFINED_MONAN_RUNTIME}")
    '/tmp/${UNDEFINED_MONAN_RUNTIME}'
    """
    return os.path.expandvars(value)


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and validate the root of a runtime manifest.

    Parameters
    ----------
    path : pathlib.Path
        Path to the runtime manifest YAML file.

    Returns
    -------
    dict of str to Any
        The value of the top-level ``runtime`` mapping.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the manifest does not contain a top-level ``runtime`` key.
    TypeError
        If ``runtime`` exists but is not a mapping.
    yaml.YAMLError
        If the file is not valid YAML.
    OSError
        If the file cannot be read.

    Notes
    -----
    Returning the ``runtime`` mapping directly keeps the rest of the code focused
    on runtime layout details.

    See Also
    --------
    build_actions : Convert the ``links`` section into action objects.
    create_directories : Create directories declared by the runtime mapping.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("runtime.yaml")
    >>> _ = path.write_text("runtime:\n  work_dir: work\n", encoding="utf-8")
    >>> load_manifest(path)["work_dir"]
    'work'
    >>> path.unlink()
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "runtime" not in data:
        raise ValueError(f"Runtime manifest must contain a 'runtime' mapping: {path}")

    runtime = data["runtime"]
    if not isinstance(runtime, dict):
        raise TypeError("runtime must be a mapping")

    return runtime


def build_actions(runtime: dict[str, Any], work_dir: Path) -> list[LinkAction]:
    """Build file actions from a runtime manifest.

    Parameters
    ----------
    runtime : dict of str to Any
        Runtime manifest mapping. The optional ``links`` key should contain
        source/target declarations.
    work_dir : pathlib.Path
        Runtime working directory. Relative targets are resolved under it.

    Returns
    -------
    list of LinkAction
        Planned file actions derived from the manifest.

    Raises
    ------
    KeyError
        If a link entry lacks required ``source`` or ``target`` keys.
    TypeError
        If ``links`` is not iterable as expected.

    Notes
    -----
    Source paths are expanded because runtime manifests commonly refer to build,
    data, or rendered-product locations through environment variables.

    See Also
    --------
    LinkAction : Dataclass representing one planned action.
    expand_value : Expand source path variables.

    Examples
    --------
    >>> runtime = {"links": [{"source": "input.yaml", "target": "config/input.yaml"}]}
    >>> build_actions(runtime, Path("work"))[0].target
    PosixPath('work/config/input.yaml')
    """
    actions: list[LinkAction] = []
    for item in runtime.get("links", []):
        source = Path(expand_value(str(item["source"])))
        target = work_dir / str(item["target"])
        actions.append(
            LinkAction(
                name=str(item.get("name", target.name)),
                source=source,
                target=target,
                required=bool(item.get("required", True)),
            )
        )
    return actions


def create_directories(runtime: dict[str, Any], work_dir: Path, dry_run: bool) -> None:
    """Create directories declared by the runtime manifest.

    Parameters
    ----------
    runtime : dict of str to Any
        Runtime manifest mapping with an optional ``directories`` list.
    work_dir : pathlib.Path
        Runtime working directory.
    dry_run : bool
        If ``True``, print planned operations without creating directories.

    Returns
    -------
    None
        The function creates directories or prints planned operations.

    Raises
    ------
    OSError
        If a directory cannot be created during real execution.

    Notes
    -----
    Directories are created with ``parents=True`` and ``exist_ok=True`` so the
    command can be re-run safely.

    See Also
    --------
    pathlib.Path.mkdir : Create directories recursively.

    Examples
    --------
    >>> create_directories({"directories": ["logs"]}, Path("work"), dry_run=True)
    [INFO] Runtime work directory: work
    [DRY-RUN] mkdir -p work/logs
    """
    print(f"[INFO] Runtime work directory: {work_dir}")
    directories = runtime.get("directories", [])
    for raw in directories:
        directory = work_dir / str(raw)
        if dry_run:
            print(f"[DRY-RUN] mkdir -p {directory}")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] Created directory: {directory}")


def apply_action(action: LinkAction, *, dry_run: bool, copy: bool, force: bool) -> bool:
    """Apply one runtime file action.

    Parameters
    ----------
    action : LinkAction
        File action to apply or simulate.
    dry_run : bool
        If ``True``, only print the planned operation.
    copy : bool
        If ``True``, copy the source file. If ``False``, create a symbolic link.
    force : bool
        If ``True``, replace existing targets before applying the action.

    Returns
    -------
    bool
        ``True`` when the action is completed, safely skipped, or accepted in
        dry-run mode. ``False`` for a missing optional file during real execution.

    Raises
    ------
    FileNotFoundError
        If a required source is missing during real execution.
    OSError
        If target removal, directory creation, copying, or linking fails.

    Notes
    -----
    Existing targets are preserved unless ``force`` is enabled. Real directories
    are removed recursively; files and symlinks are unlinked directly.

    See Also
    --------
    LinkAction : Runtime action data structure.
    shutil.copy2 : Copy files with metadata preservation.
    pathlib.Path.symlink_to : Create symbolic links.

    Examples
    --------
    >>> action = LinkAction("missing", Path("missing.file"), Path("work/missing.file"), False)
    >>> apply_action(action, dry_run=False, copy=False, force=False)
    [WARN] Missing source for missing: missing.file
    False
    """
    if not action.source.exists():
        message = f"[WARN] Missing source for {action.name}: {action.source}"
        if action.required and not dry_run:
            raise FileNotFoundError(message)
        print(message if not action.required else message + " (required; allowed in dry-run)")
        if not dry_run:
            return False

    if dry_run:
        verb = "cp" if copy else "ln -s"
        print(f"[DRY-RUN] {verb} {action.source} {action.target}")
        return True

    action.target.parent.mkdir(parents=True, exist_ok=True)
    if action.target.exists() or action.target.is_symlink():
        if action.target.is_symlink() and not copy:
            current = action.target.resolve()
            desired = action.source.resolve()
            if current != desired:
                action.target.unlink()
                action.target.symlink_to(action.source)
                print(f"[INFO] Updated stale symlink for {action.name}: {action.source} -> {action.target}")
                return True
        if not force:
            print(f"[INFO] Target already exists, keeping: {action.target}")
            return True
        if action.target.is_dir() and not action.target.is_symlink():
            shutil.rmtree(action.target)
        else:
            action.target.unlink()

    if copy:
        shutil.copy2(action.source, action.target)
        print(f"[INFO] Copied {action.name}: {action.source} -> {action.target}")
    else:
        action.target.symlink_to(action.source)
        print(f"[INFO] Linked {action.name}: {action.source} -> {action.target}")
    return True


def main() -> int:
    """Run the runtime preparation command-line interface.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all required actions are valid or
        completed. Returns ``2`` when one or more required file actions fail.

    Raises
    ------
    FileNotFoundError
        If the manifest or a required runtime source is missing.
    yaml.YAMLError
        If the manifest cannot be parsed as YAML.
    OSError
        If runtime directories or file actions cannot be created.

    Notes
    -----
    ``--work-dir`` overrides the manifest ``work_dir`` value. This is useful when
    testing the same rendered manifest in a temporary directory.

    See Also
    --------
    load_manifest : Load and validate the runtime manifest root.
    create_directories : Create runtime directories.
    build_actions : Build planned file actions.
    apply_action : Apply one file action.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Prepare runtime directory for MONAN/JEDI experiments.")
    parser.add_argument("manifest", type=Path, help="Runtime manifest YAML")
    parser.add_argument("--work-dir", type=Path, help="Override runtime work directory")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without creating links")
    parser.add_argument("--copy", action="store_true", help="Copy files instead of creating symlinks")
    parser.add_argument("--force", action="store_true", help="Replace existing targets")
    args = parser.parse_args()

    runtime = load_manifest(args.manifest)
    work_dir = args.work_dir or Path(expand_value(str(runtime["work_dir"])))

    create_directories(runtime, work_dir, args.dry_run)

    actions = build_actions(runtime, work_dir)
    print(f"[INFO] Planned file actions: {len(actions)}")
    ok = True
    for action in actions:
        try:
            ok = apply_action(action, dry_run=args.dry_run, copy=args.copy, force=args.force) and ok
        except FileNotFoundError as exc:
            print(f"[ERROR] {exc}")
            ok = False

    rendered = runtime.get("rendered", {})
    if rendered:
        print("[INFO] Rendered products declared by manifest:")
        for key, value in rendered.items():
            print(f"  - {key}: {value}")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
