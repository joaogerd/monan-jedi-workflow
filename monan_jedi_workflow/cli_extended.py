"""Additional cycle commands layered over the stable MONAN-JEDI CLI."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import cli as legacy
from .init_stage import prepare_mpas_init, submit_mpas_init, validate_mpas_init, wait_mpas_init
from .wps_stage import prepare_wps, run_wps, validate_wps

_NEW = {
    "wps-prepare", "wps-run", "wps-validate",
    "mpas-init-prepare", "mpas-init-submit", "mpas-init-wait", "mpas-init-validate",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monan-jedi-workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("wps-prepare", "wps-validate", "mpas-init-prepare", "mpas-init-wait", "mpas-init-validate"):
        item = sub.add_parser(name)
        item.add_argument("config_dir", type=Path)
        item.add_argument("--cycle", required=True)
        if name == "mpas-init-wait":
            item.add_argument("--poll-seconds", type=int, default=30)
    run = sub.add_parser("wps-run")
    run.add_argument("config_dir", type=Path)
    run.add_argument("--cycle", required=True)
    run.add_argument("--force", action="store_true")
    submit = sub.add_parser("mpas-init-submit")
    submit.add_argument("config_dir", type=Path)
    submit.add_argument("--cycle", required=True)
    submit.add_argument("--wait", action="store_true")
    submit.add_argument("--resubmit", action="store_true")
    submit.add_argument("--poll-seconds", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in _NEW:
        return legacy.main(argv)
    args = _parser().parse_args(argv)
    if args.command == "wps-prepare":
        prepare_wps(args.config_dir, args.cycle)
    elif args.command == "wps-run":
        run_wps(args.config_dir, args.cycle, force=args.force)
    elif args.command == "wps-validate":
        validate_wps(args.config_dir, args.cycle)
    elif args.command == "mpas-init-prepare":
        prepare_mpas_init(args.config_dir, args.cycle)
    elif args.command == "mpas-init-submit":
        submit_mpas_init(args.config_dir, args.cycle, wait=args.wait, resubmit=args.resubmit, poll_seconds=args.poll_seconds)
    elif args.command == "mpas-init-wait":
        wait_mpas_init(args.config_dir, args.cycle, poll_seconds=args.poll_seconds)
    elif args.command == "mpas-init-validate":
        validate_mpas_init(args.config_dir, args.cycle)
    return 0
