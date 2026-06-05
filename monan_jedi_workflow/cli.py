"""Command-line interface for the minimal MONAN-JEDI workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_experiment_config, validate_experiment_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monan-jedi-workflow",
        description="Minimal Python-first workflow for MONAN MPAS-JEDI experiments.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-config",
        help="Validate split YAML configuration files for one experiment.",
    )
    validate_parser.add_argument(
        "config_dir",
        type=Path,
        help="Experiment configuration directory.",
    )

    return parser


def run_validate_config(config_dir: Path) -> int:
    config = load_experiment_config(config_dir)
    messages = validate_experiment_config(config)

    for message in messages:
        print(f"[OK] {message}")

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate-config":
        return run_validate_config(args.config_dir)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
