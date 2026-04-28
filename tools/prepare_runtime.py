#!/usr/bin/env python3
"""Prepare a MONAN-JEDI-WORKFLOW runtime directory.

This utility creates the directory layout and links/copies files required by a rendered
3DVar-FGAT experiment. It is deliberately separated from the JEDI execution step so the runtime
layout can be validated before launching expensive HPC jobs.
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
    """A file link/copy action requested by the runtime manifest."""

    name: str
    source: Path
    target: Path
    required: bool


def expand_value(value: str) -> str:
    """Expand environment variables in a string."""
    return os.path.expandvars(value)


def load_manifest(path: Path) -> dict[str, Any]:
    """Load a runtime manifest YAML file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "runtime" not in data:
        raise ValueError(f"Runtime manifest must contain a 'runtime' mapping: {path}")
    runtime = data["runtime"]
    if not isinstance(runtime, dict):
        raise TypeError("runtime must be a mapping")
    return runtime


def build_actions(runtime: dict[str, Any], work_dir: Path) -> list[LinkAction]:
    """Build link actions from manifest."""
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
    """Create required runtime directories."""
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
    """Apply one link/copy action.

    Returns True if the action is valid or was completed, False for a non-fatal missing optional file.
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
