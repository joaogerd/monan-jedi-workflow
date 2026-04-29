#!/usr/bin/env python3
"""Check observer metadata coverage for an experiment manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check observer metadata coverage.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/observers.yaml"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("configs/jedi/obs_plugs/variational/metadata.yaml"),
    )
    args = parser.parse_args()

    manifest = read_yaml(args.manifest)
    metadata = read_yaml(args.metadata)

    observers = manifest.get("observers") if isinstance(manifest, dict) else None
    registry = metadata.get("observer_plugs") if isinstance(metadata, dict) else None

    if not isinstance(observers, list):
        print("[ERROR] Manifest does not contain an observers list")
        return 2
    if not isinstance(registry, dict):
        print("[ERROR] Metadata does not contain observer_plugs mapping")
        return 2

    required_keys = {
        "template",
        "status",
        "category",
        "expected_ioda_group",
        "requires_bias_correction",
        "validated_on_jaci",
        "notes",
    }

    ok = True
    for entry in observers:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str):
            print("[ERROR] Invalid observer entry in manifest")
            ok = False
            continue
        item = registry.get(name)
        if not isinstance(item, dict):
            print(f"[ERROR] Missing metadata for observer: {name}")
            ok = False
            continue
        missing = sorted(required_keys - set(item.keys()))
        if missing:
            print(f"[ERROR] Metadata for {name} is missing keys: {', '.join(missing)}")
            ok = False
            continue
        if item["template"] != entry.get("template"):
            print(f"[ERROR] Template mismatch for {name}")
            ok = False
            continue
        print(
            f"[INFO] Observer metadata: {name} "
            f"status={item['status']} category={item['category']} "
            f"validated_on_jaci={item['validated_on_jaci']}"
        )

    if not ok:
        return 2

    print("[INFO] Observer metadata coverage check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
