"""Command-line interface for the minimal MONAN-JEDI workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_experiment_config, validate_experiment_config
from .runtime import prepare_runtime
from .render import write_rendered_yaml, write_rendered_pbs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monan-jedi-workflow",
        description="Minimal Python-first workflow for MONAN MPAS-JEDI experiments.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    for cmd in ["validate-config", "prepare-runtime", "render-yaml", "render-pbs"]:
        p = sub.add_parser(cmd)
        p.add_argument("config_dir", type=Path)

    return parser


def run_validate(config_dir: Path) -> int:
    cfg = load_experiment_config(config_dir)

    for msg in validate_experiment_config(cfg):
        print(f"[OK] {msg}")

    return 0


def run_prepare(config_dir: Path) -> int:
    cfg = load_experiment_config(config_dir)

    for msg in validate_experiment_config(cfg):
        print(f"[OK] {msg}")

    for msg in prepare_runtime(cfg):
        print(msg)

    return 0


def run_render_yaml(config_dir: Path) -> int:
    cfg = load_experiment_config(config_dir)
    path = write_rendered_yaml(cfg)
    print(f"[OK] rendered YAML: {path}")
    return 0


def run_render_pbs(config_dir: Path) -> int:
    cfg = load_experiment_config(config_dir)
    path = write_rendered_pbs(cfg)
    print(f"[OK] rendered PBS: {path}")
    return 0


def main() -> int:

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate-config":
        return run_validate(args.config_dir)

    if args.command == "prepare-runtime":
        return run_prepare(args.config_dir)

    if args.command == "render-yaml":
        return run_render_yaml(args.config_dir)

    if args.command == "render-pbs":
        return run_render_pbs(args.config_dir)

    parser.error("invalid command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
