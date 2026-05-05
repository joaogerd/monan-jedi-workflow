#!/usr/bin/env python3
"""Check consistency between input source registry, staging manifest and checklist."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def by_name(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label} entry missing valid name")
        if name in result:
            raise ValueError(f"duplicate {label} entry: {name}")
        result[name] = item
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check consistency between MONAN/JEDI input configuration files."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/input_sources.example.yaml"),
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/staging.example.yaml"),
    )
    parser.add_argument(
        "--checklist",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/scientific_input_checklist.yaml"),
    )
    args = parser.parse_args()

    sources_doc = read_yaml(args.sources)
    staging_doc = read_yaml(args.staging)
    checklist_doc = read_yaml(args.checklist)

    sources_root = sources_doc.get("input_sources") if isinstance(sources_doc, dict) else None
    staging_root = staging_doc.get("input_staging") if isinstance(staging_doc, dict) else None
    checklist_root = (
        checklist_doc.get("scientific_input_checklist") if isinstance(checklist_doc, dict) else None
    )

    if not isinstance(sources_root, dict):
        print("[ERROR] sources file must contain input_sources mapping")
        return 2
    if not isinstance(staging_root, dict):
        print("[ERROR] staging file must contain input_staging mapping")
        return 2
    if not isinstance(checklist_root, dict):
        print("[ERROR] checklist file must contain scientific_input_checklist mapping")
        return 2

    try:
        sources = by_name(sources_root.get("sources", []), "source")
        staging = by_name(staging_root.get("files", []), "staging")
        checklist = by_name(checklist_root.get("inputs", []), "checklist")
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    ok = True

    source_names = set(sources)
    staging_names = set(staging)
    checklist_names = set(checklist)

    missing_in_staging = sorted(source_names - staging_names)
    missing_in_checklist = sorted(source_names - checklist_names)
    extra_in_staging = sorted(staging_names - source_names)
    extra_in_checklist = sorted(checklist_names - source_names)

    for name in missing_in_staging:
        print(f"[ERROR] Source missing from staging manifest: {name}")
        ok = False
    for name in missing_in_checklist:
        print(f"[ERROR] Source missing from scientific checklist: {name}")
        ok = False
    for name in extra_in_staging:
        print(f"[ERROR] Staging entry missing from source registry: {name}")
        ok = False
    for name in extra_in_checklist:
        print(f"[ERROR] Checklist entry missing from source registry: {name}")
        ok = False

    for name in sorted(source_names & staging_names & checklist_names):
        source = sources[name]
        stage = staging[name]
        check = checklist[name]

        source_external_target = source.get("external_target")
        source_staged_target = source.get("staged_target")
        staging_target = stage.get("target")
        checklist_target = check.get("target")

        if source_external_target != staging_target:
            print(
                f"[ERROR] external/staging target mismatch for {name}: "
                f"source external_target={source_external_target!r} staging target={staging_target!r}"
            )
            ok = False

        if source_staged_target != checklist_target:
            print(
                f"[ERROR] staged/checklist target mismatch for {name}: "
                f"source staged_target={source_staged_target!r} checklist target={checklist_target!r}"
            )
            ok = False

        if bool(source.get("required", True)) != bool(stage.get("required", True)):
            print(f"[ERROR] required flag mismatch between source and staging for {name}")
            ok = False

        if bool(source.get("required", True)) != bool(check.get("required", True)):
            print(f"[ERROR] required flag mismatch between source and checklist for {name}")
            ok = False

        if source.get("kind") != stage.get("kind"):
            print(f"[ERROR] kind mismatch between source and staging for {name}")
            ok = False

        if source.get("kind") != check.get("kind"):
            print(f"[ERROR] kind mismatch between source and checklist for {name}")
            ok = False

        if ok:
            pass
        print(f"[INFO] Consistency checked: {name}")

    if not ok:
        return 2

    print("[INFO] Input source/staging/checklist consistency check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
