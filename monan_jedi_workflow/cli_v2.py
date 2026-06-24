"""Public command-line dispatch for MONAN-JEDI workflow stages."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_experiment_config, validate_experiment_config
from .pbs import submit as submit_pbs
from .pbs import wait as wait_pbs
from .render import write_rendered_pbs, write_rendered_yaml
from .run_validation import validate_run
from .runtime import prepare_runtime


def _add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("config_dir", type=Path)


def build_parser() -> argparse.ArgumentParser:
    """Build the small, explicit MONAN-JEDI command surface."""
    parser = argparse.ArgumentParser(
        prog="monan-jedi-workflow",
        description="Python-first workflow stages for MONAN MPAS-JEDI experiments.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("validate-config", "prepare-runtime", "render-yaml", "render-pbs", "validate-run"):
        command_parser = sub.add_parser(command)
        _add_config_argument(command_parser)

    submit_parser = sub.add_parser("submit")
    _add_config_argument(submit_parser)
    submit_parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the submitted PBS job to leave qstat before returning.",
    )
    submit_parser.add_argument(
        "--resubmit",
        action="store_true",
        help="Submit a new PBS job even when a submission manifest already exists.",
    )
    submit_parser.add_argument("--poll-seconds", type=int, default=30)
    submit_parser.add_argument("--timeout-seconds", type=int)

    wait_parser = sub.add_parser("wait")
    _add_config_argument(wait_parser)
    wait_parser.add_argument("--poll-seconds", type=int, default=30)
    wait_parser.add_argument("--timeout-seconds", type=int)

    return parser


def run_validate(config_dir: Path) -> int:
    config = load_experiment_config(config_dir)
    for message in validate_experiment_config(config):
        print(f"[OK] {message}")
    return 0


def run_prepare(config_dir: Path) -> int:
    config = load_experiment_config(config_dir)
    for message in validate_experiment_config(config):
        print(f"[OK] {message}")
    for message in prepare_runtime(config):
        print(message)
    return 0


def run_render_yaml(config_dir: Path) -> int:
    config = load_experiment_config(config_dir)
    path = write_rendered_yaml(config)
    print(f"[OK] rendered YAML: {path}")
    return 0


def run_render_pbs(config_dir: Path) -> int:
    config = load_experiment_config(config_dir)
    path = write_rendered_pbs(config)
    print(f"[OK] rendered PBS: {path}")
    return 0


def run_submit(
    config_dir: Path,
    *,
    wait: bool = False,
    resubmit: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> int:
    config = load_experiment_config(config_dir)
    submit_pbs(config, resubmit=resubmit)
    if wait:
        wait_pbs(
            config,
            poll_seconds=poll_seconds,
            timeout_seconds=timeout_seconds,
        )
    return 0


def run_wait(
    config_dir: Path,
    *,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> int:
    config = load_experiment_config(config_dir)
    wait_pbs(config, poll_seconds=poll_seconds, timeout_seconds=timeout_seconds)
    return 0


def run_validate_run(config_dir: Path) -> int:
    config = load_experiment_config(config_dir)
    validate_run(config)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-config":
        return run_validate(args.config_dir)
    if args.command == "prepare-runtime":
        return run_prepare(args.config_dir)
    if args.command == "render-yaml":
        return run_render_yaml(args.config_dir)
    if args.command == "render-pbs":
        return run_render_pbs(args.config_dir)
    if args.command == "submit":
        return run_submit(
            args.config_dir,
            wait=args.wait,
            resubmit=args.resubmit,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    if args.command == "wait":
        return run_wait(
            args.config_dir,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    if args.command == "validate-run":
        return run_validate_run(args.config_dir)
    parser = build_parser()
    parser.error("invalid command")
    return 2
