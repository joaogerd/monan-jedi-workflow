"""Additional cycle commands layered over the stable MONAN-JEDI CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import cli as legacy
from .campaign import (
    check_campaign,
    create_campaign,
    run_campaign,
    status_campaign,
    tui_campaign,
)
from .corrected_campaign import materialize_corrected_campaign
from .corrected_replay import materialize_corrected_replay
from .init_stage import (
    prepare_mpas_init,
    submit_mpas_init,
    validate_mpas_init,
    wait_mpas_init,
)
from .netcdf_compare import main as compare_netcdf_main
from .validation_gate import require_valid_manifest
from .wps_stage import prepare_wps, run_wps, validate_wps

_NEW = {
    "wps-prepare",
    "wps-run",
    "wps-validate",
    "mpas-init-prepare",
    "mpas-init-submit",
    "mpas-init-wait",
    "mpas-init-validate",
    "compare-netcdf",
    "validation-gate",
    "materialize-corrected-replay",
    "materialize-corrected-campaign",
    "campaign",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monan-jedi-workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "wps-prepare",
        "wps-validate",
        "mpas-init-prepare",
        "mpas-init-wait",
        "mpas-init-validate",
    ):
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

    gate = sub.add_parser(
        "validation-gate",
        help="require one stage validation manifest to contain valid=true",
    )
    gate.add_argument("manifest", type=Path)

    replay = sub.add_parser(
        "materialize-corrected-replay",
        help="create a clean 2018-04-15 00Z->18Z simpleWorkflow replay case",
    )
    replay.add_argument("--initial-jedi-case", required=True, type=Path)
    replay.add_argument("--cycling-jedi-case", required=True, type=Path)
    replay.add_argument("--mpas-case", required=True, type=Path)
    replay.add_argument("--obs2ioda-config", required=True, type=Path)
    replay.add_argument("--workflow-template", required=True, type=Path)
    replay.add_argument("--destination", required=True, type=Path)

    materialize = sub.add_parser(
        "materialize-corrected-campaign",
        help=(
            "developer command: create a compact native-cycle campaign for an "
            "arbitrary 6-hourly analysis period"
        ),
    )
    materialize.add_argument(
        "--initial-jedi-case",
        type=Path,
        default=None,
        help="legacy source-compatibility argument; no precomputed first background is consumed",
    )
    materialize.add_argument("--cycling-jedi-case", required=True, type=Path)
    materialize.add_argument(
        "--initial-mpas-case",
        required=True,
        type=Path,
        help="standalone MPAS case whose integration creates the first background",
    )
    materialize.add_argument("--mpas-case", required=True, type=Path)
    materialize.add_argument("--obs2ioda-config", required=True, type=Path)
    materialize.add_argument(
        "--start-cycle",
        default="2018-04-15T00:00:00Z",
        help="first analysis cycle (must be aligned to 00/06/12/18Z)",
    )
    materialize.add_argument("--end-cycle", required=True)
    materialize.add_argument("--destination", required=True, type=Path)
    materialize.add_argument(
        "--run-mpas-on-last-cycle",
        action="store_true",
        help="run MPAS from the final analysis when a forecast is scientifically requested",
    )

    campaign = sub.add_parser(
        "campaign",
        help="check, create, run, resume and monitor a campaign from one YAML file",
    )
    campaign_sub = campaign.add_subparsers(dest="campaign_command", required=True)
    for action, help_text in (
        ("check", "verify all campaign inputs without submitting work"),
        ("create", "preflight and materialize the campaign without running it"),
        ("run", "preflight, create if needed, and run or resume the campaign"),
        ("status", "show simpleWorkflow status for an existing campaign"),
        ("tui", "open the interactive simpleWorkflow monitor for a campaign"),
    ):
        item = campaign_sub.add_parser(action, help=help_text)
        item.add_argument("config", type=Path, help="campaign YAML file")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in _NEW:
        return legacy.main(argv)
    if argv[0] == "compare-netcdf":
        return compare_netcdf_main(argv[1:])

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
        submit_mpas_init(
            args.config_dir,
            args.cycle,
            wait=args.wait,
            resubmit=args.resubmit,
            poll_seconds=args.poll_seconds,
        )
    elif args.command == "mpas-init-wait":
        wait_mpas_init(args.config_dir, args.cycle, poll_seconds=args.poll_seconds)
    elif args.command == "mpas-init-validate":
        validate_mpas_init(args.config_dir, args.cycle)
    elif args.command == "validation-gate":
        require_valid_manifest(args.manifest)
        print(f"[OK] validation manifest accepted: {args.manifest}")
    elif args.command == "materialize-corrected-replay":
        path = materialize_corrected_replay(
            initial_jedi_case=args.initial_jedi_case,
            cycling_jedi_case=args.cycling_jedi_case,
            mpas_case=args.mpas_case,
            obs2ioda_config=args.obs2ioda_config,
            workflow_template=args.workflow_template,
            destination=args.destination,
        )
        print(f"[OK] materialized corrected replay case: {path}")
    elif args.command == "materialize-corrected-campaign":
        path = materialize_corrected_campaign(
            initial_jedi_case=args.initial_jedi_case,
            cycling_jedi_case=args.cycling_jedi_case,
            initial_mpas_case=args.initial_mpas_case,
            mpas_case=args.mpas_case,
            obs2ioda_config=args.obs2ioda_config,
            start_cycle=args.start_cycle,
            end_cycle=args.end_cycle,
            destination=args.destination,
            run_mpas_on_last_cycle=args.run_mpas_on_last_cycle,
        )
        print(f"[OK] materialized corrected campaign: {path}")
    elif args.command == "campaign":
        if args.campaign_command == "check":
            report = check_campaign(args.config)
            return 0 if report.valid else 2
        if args.campaign_command == "create":
            create_campaign(args.config)
        elif args.campaign_command == "run":
            return run_campaign(args.config)
        elif args.campaign_command == "status":
            return status_campaign(args.config)
        elif args.campaign_command == "tui":
            return tui_campaign(args.config)
    return 0
