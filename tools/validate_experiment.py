#!/usr/bin/env python3
"""Validate a MONAN-JEDI-WORKFLOW experiment structure.

This validator is intentionally lightweight. It checks that the experiment configuration files
exist, contain the expected top-level sections, and that rendered products were generated.
It does not validate scientific correctness or JEDI schema.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


class ValidationError(RuntimeError):
    """Raised when a validation check fails."""


def load_yaml(path: Path) -> Any:
    """Load YAML from path."""
    if not path.is_file():
        raise ValidationError(f"Missing YAML file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def require_mapping(data: Any, path: Path) -> dict[str, Any]:
    """Require YAML content to be a mapping."""
    if not isinstance(data, dict):
        raise ValidationError(f"YAML file must contain a mapping: {path}")
    return data


def check_top_key(path: Path, key: str) -> None:
    """Check that a YAML file has a top-level key."""
    data = require_mapping(load_yaml(path), path)
    if key not in data:
        raise ValidationError(f"Missing top-level key '{key}' in {path}")
    print(f"[INFO] {path}: found top-level key '{key}'")


def check_file_contains(path: Path, needles: list[str]) -> None:
    """Check that a file contains required strings."""
    if not path.is_file():
        raise ValidationError(f"Missing file: {path}")
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise ValidationError(f"Missing expected text in {path}: {needle}")
    print(f"[INFO] {path}: content check passed")


def check_file_contains_any(path: Path, alternatives: list[str], label: str) -> None:
    """Check that a file contains at least one expected alternative string."""
    if not path.is_file():
        raise ValidationError(f"Missing file: {path}")
    text = path.read_text(encoding="utf-8")
    if not any(item in text for item in alternatives):
        joined = " OR ".join(alternatives)
        raise ValidationError(f"Missing expected {label} in {path}: {joined}")
    print(f"[INFO] {path}: found {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MONAN/JEDI experiment structure.")
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat"),
        help="Experiment configuration directory.",
    )
    parser.add_argument(
        "--rendered-dir",
        type=Path,
        default=Path("build/rendered"),
        help="Rendered output directory.",
    )
    args = parser.parse_args()

    exp = args.experiment_dir
    rendered = args.rendered_dir

    checks = [
        (exp / "experiment.yaml", "experiment"),
        (exp / "observers.yaml", "observers"),
        (exp / "runtime_manifest.example.yaml", "runtime"),
        (exp / "run_command.example.yaml", "variational_run"),
        (exp / "pbs_job.example.yaml", "pbs"),
    ]

    try:
        for path, key in checks:
            check_top_key(path, key)

        check_file_contains(
            rendered / "3dvar_fgat.yaml",
            ["cost type: 3D-Var", "observers:", "aircraft", "sondes", "sfc"],
        )
        check_file_contains(
            rendered / "observers.yaml",
            ["name: aircraft", "name: sondes", "name: sfc"],
        )
        check_file_contains_any(
            rendered / "mpasjedi_variational.command",
            ["mpasjedi_variational", "MPASJEDI_VARIATIONAL_EXE"],
            "variational executable reference",
        )
        check_file_contains(
            rendered / "mpasjedi_variational.command",
            ["3dvar_fgat.yaml"],
        )
        check_file_contains(
            rendered / "3dvar_fgat.pbs",
            ["#PBS -N", "#PBS -l select=", "run_3dvar_fgat_variational.sh"],
        )
    except ValidationError as exc:
        print(f"[ERROR] {exc}")
        return 2

    print("[INFO] Experiment structural validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
