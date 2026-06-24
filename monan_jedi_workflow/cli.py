"""Public command-line interface for MONAN-JEDI experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_experiment_config, validate_experiment_config
from .mpas_stage import prepare_mpas, submit_mpas, validate_mpas, wait_mpas
from .obs2ioda_stage import (
    doctor_obs2ioda,
    prepare_obs2ioda,
    run_obs2ioda,
    validate_obs2ioda,
)
from .render import write_rendered_pbs, write_rendered_yaml
from .run_validation import validate_run
from .runtime import prepare_runtime
from .scheduler import submit as submit_pbs
from .scheduler import wait as wait_pbs


def _add_config_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("config_dir", type=Path)


def _add_wait_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=None)


def _add_cycle_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cycle",
        required=True,
        metavar="TIME",
        help="ISO-8601 analysis or forecast cycle, for example 2018-04-15T00:00:00Z.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monan-jedi-workflow",
        description="Python-first workflow commands for MONAN MPAS-JEDI experiments.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for command in (
        "validate-config",
        "prepare-runtime",
        "render-yaml",
        "render-pbs",
        "validate-run",
    ):
        _add_config_dir(sub.add_parser(command))

    submit_parser = sub.add_parser("submit")
    _add_config_dir(submit_parser)
    submit_parser.add_argument("--wait", action="store_true")
    submit_parser.add_argument("--resubmit", action="store_true")
    _add_wait_options(submit_parser)

    wait_parser = sub.add_parser("wait")
    _add_config_dir(wait_parser)
    _add_wait_options(wait_parser)

    mpas_prepare = sub.add_parser("mpas-prepare")
    _add_config_dir(mpas_prepare)
    _add_cycle_argument(mpas_prepare)

    mpas_submit = sub.add_parser("mpas-submit")
    _add_config_dir(mpas_submit)
    _add_cycle_argument(mpas_submit)
    mpas_submit.add_argument("--wait", action="store_true")
    mpas_submit.add_argument("--resubmit", action="store_true")
    _add_wait_options(mpas_submit)

    mpas_wait = sub.add_parser("mpas-wait")
    _add_config_dir(mpas_wait)
    _add_cycle_argument(mpas_wait)
    _add_wait_options(mpas_wait)

    mpas_validate = sub.add_parser("mpas-validate")
    _add_config_dir(mpas_validate)
    _add_cycle_argument(mpas_validate)

    obs_doctor = sub.add_parser("obs2ioda-doctor")
    _add_config_dir(obs_doctor)
    _add_cycle_argument(obs_doctor)

    obs_prepare = sub.add_parser("obs2ioda-prepare")
    _add_config_dir(obs_prepare)
    _add_cycle_argument(obs_prepare)
    obs_prepare.add_argument(
        "--refresh",
        action="store_true",
        help="Replace a non-successful conversion plan after configuration corrections.",
    )

    obs_run = sub.add_parser("obs2ioda-run")
    _add_config_dir(obs_run)
    _add_cycle_argument(obs_run)
    obs_run.add_argument("--force", action="store_true")

    obs_validate = sub.add_parser("obs2ioda-validate")
    _add_config_dir(obs_validate)
    _add_cycle_argument(obs_validate)

    return parser


def _load_and_validate(config_dir: Path):
    config = load_experiment_config(config_dir)
    validate_experiment_config(config)
    return config


def run_validate(config_dir: Path) -> int:
    config = load_experiment_config(config_dir)
    for message in validate_experiment_config(config):
        print(f"[OK] {message}")
    return 0


def run_prepare(config_dir: Path) -> int:
    config = _load_and_validate(config_dir)
    for message in prepare_runtime(config):
        print(message)
    return 0


def run_render_yaml(config_dir: Path) -> int:
    config = _load_and_validate(config_dir)
    path = write_rendered_yaml(config)
    print(f"[OK] rendered YAML: {path}")
    return 0


def run_render_pbs(config_dir: Path) -> int:
    config = _load_and_validate(config_dir)
    path = write_rendered_pbs(config)
    print(f"[OK] rendered PBS: {path}")
    return 0


def run_submit(
    config_dir: Path,
    *,
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
    resubmit: bool = False,
) -> int:
    config = _load_and_validate(config_dir)
    submit_pbs(config, resubmit=resubmit)
    if wait:
        wait_pbs(config, poll_seconds=poll_seconds, timeout_seconds=timeout_seconds)
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
    validate_run(load_experiment_config(config_dir))
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
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
            resubmit=args.resubmit,
        )
    if args.command == "wait":
        return run_wait(
            args.config_dir,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    if args.command == "validate-run":
        return run_validate_run(args.config_dir)
    if args.command == "mpas-prepare":
        prepare_mpas(args.config_dir, args.cycle)
        return 0
    if args.command == "mpas-submit":
        submit_mpas(
            args.config_dir,
            args.cycle,
            wait=args.wait,
            resubmit=args.resubmit,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
        )
        return 0
    if args.command == "mpas-wait":
        wait_mpas(
            args.config_dir,
            args.cycle,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_seconds,
        )
        return 0
    if args.command == "mpas-validate":
        validate_mpas(args.config_dir, args.cycle)
        return 0
    if args.command == "obs2ioda-doctor":
        doctor_obs2ioda(args.config_dir, args.cycle)
        return 0
    if args.command == "obs2ioda-prepare":
        prepare_obs2ioda(args.config_dir, args.cycle, refresh=args.refresh)
        return 0
    if args.command == "obs2ioda-run":
        run_obs2ioda(args.config_dir, args.cycle, force=args.force)
        return 0
    if args.command == "obs2ioda-validate":
        validate_obs2ioda(args.config_dir, args.cycle)
        return 0
    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
