#!/usr/bin/env python3
"""Check observer manifest consistency."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="Check observer manifest consistency.")
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/observers.yaml"),
    )
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"[ERROR] Missing manifest: {args.manifest}")
        return 2

    data = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("observers"), list):
        print("[ERROR] Manifest must contain an observers list")
        return 2

    seen = set()
    for entry in data["observers"]:
        if not isinstance(entry, dict):
            print("[ERROR] Each observer entry must be a mapping")
            return 2
        name = entry.get("name")
        template = entry.get("template")
        enabled = entry.get("enabled")
        if not isinstance(name, str) or not name:
            print("[ERROR] Invalid observer name")
            return 2
        if name in seen:
            print(f"[ERROR] Duplicate observer name: {name}")
            return 2
        seen.add(name)
        if not isinstance(template, str) or not template:
            print(f"[ERROR] Invalid template for observer: {name}")
            return 2
        if not isinstance(enabled, bool):
            print(f"[ERROR] Invalid enabled flag for observer: {name}")
            return 2
        template_path = Path(template)
        if not template_path.is_file():
            print(f"[ERROR] Missing template for observer {name}: {template_path}")
            return 2
        text = template_path.read_text(encoding="utf-8")
        if name not in text:
            print(f"[ERROR] Observer name not found in template {template_path}: {name}")
            return 2
        print(f"[INFO] Observer entry validated: {name}")

    print("[INFO] Observer manifest check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
