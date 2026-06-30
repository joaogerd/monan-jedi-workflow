"""Additional high-level commands layered over the stable MONAN-JEDI CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import cli as legacy
from .init_stage import prepare_mpas_init, submit_mpas_init, validate_mpas_init, wait_mpas_init
from .input_sources import fetch_input_source, resolve_input_source, validate_input_source, write_input_report
from .workflow_plan import (
    build_workflow_plan,
    execute_workflow,
    export_bmatrix_contract,
    validate_and_record_inputs,
    validate_workflow_plan,
    workflow_state_path,
    write_workflow_plan,
)
from .wps_stage import prepare_wps, run_wps, validate_wps

_NEW = {
    "wps-prepare", "wps-run", "wps-validate",
    "mpas-init-prepare", "mpas-init-submit", "mpas-init-wait", "mpas-init-validate",
    "input-validate", "input-fetch",
    "workflow-validate", "workflow-plan", "workflow-status", "workflow-run", "prepare-bmatrix",
}


def _with_cycle(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("config_dir", type=Path)
    parser.add_argument("--cycle", required=True, help="Timezone-aware ISO-8601 cycle, e.g. 2018-04-15T00:00:00Z.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monan-jedi-workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("wps-prepare", "wps-validate", "mpas-init-prepare", "mpas-init-wait", "mpas-init-validate"):
        item = sub.add_parser(name)
        _with_cycle(item)
        if name == "mpas-init-wait":
            item.add_argument("--poll-seconds", type=int, default=30)
    run = sub.add_parser("wps-run")
    _with_cycle(run)
    run.add_argument("--force", action="store_true")
    submit = sub.add_parser("mpas-init-submit")
    _with_cycle(submit)
    submit.add_argument("--wait", action="store_true")
    submit.add_argument("--resubmit", action="store_true")
    submit.add_argument("--poll-seconds", type=int, default=30)

    for name in ("input-validate", "input-fetch"):
        item = sub.add_parser(name)
        _with_cycle(item)
        item.add_argument("--source", required=True)
        if name == "input-validate":
            item.add_argument("--checksum", action="store_true")
        else:
            item.add_argument("--overwrite", action="store_true")

    for name in ("workflow-validate", "workflow-plan", "workflow-status", "prepare-bmatrix"):
        item = sub.add_parser(name)
        _with_cycle(item)
        item.add_argument("--checksum", action="store_true")
        if name == "workflow-plan":
            item.add_argument("--force", action="store_true")
    workflow_run = sub.add_parser("workflow-run")
    _with_cycle(workflow_run)
    workflow_run.add_argument("--execute", action="store_true", help="Execute the next safe frontier; default is dry-run.")
    workflow_run.add_argument("--submit", action="store_true", help="Permit explicit PBS submission after preparation.")
    workflow_run.add_argument("--resubmit", action="store_true", help="Permit replacing a prior scheduler submission.")
    workflow_run.add_argument("--fetch-inputs", action="store_true", help="Permit explicit retrieval for remote configured providers.")
    return parser


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


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
    elif args.command in {"input-validate", "input-fetch"}:
        source = resolve_input_source(args.config_dir, args.source, args.cycle)
        if args.command == "input-fetch":
            path = fetch_input_source(source, overwrite=args.overwrite)
            _emit({"fetched": str(path), "source": source.name})
        else:
            report = validate_input_source(source, with_checksum=args.checksum)
            path = write_input_report(args.config_dir, source, report)
            _emit({"report": str(path), **report})
    else:
        plan = build_workflow_plan(args.config_dir, args.cycle)
        if args.command == "workflow-validate":
            _emit(validate_workflow_plan(plan, with_checksum=args.checksum))
        elif args.command == "workflow-plan":
            path = write_workflow_plan(plan, force=args.force)
            _emit({"plan": str(path), "fingerprint": plan.fingerprint, "steps": [step.name for step in plan.steps]})
        elif args.command == "workflow-status":
            path = workflow_state_path(plan)
            _emit({"plan": str(path), "exists": path.is_file(), "steps": [step.name for step in plan.steps]})
        elif args.command == "prepare-bmatrix":
            validate_and_record_inputs(plan, with_checksum=args.checksum)
            _emit({"handoff": str(export_bmatrix_contract(plan, with_checksum=args.checksum))})
        elif args.command == "workflow-run":
            if not args.execute:
                path = write_workflow_plan(plan)
                _emit({"dry_run": True, "plan": str(path), "steps": [step.name for step in plan.steps]})
            else:
                _emit({"dry_run": False, "execution": str(execute_workflow(plan, submit=args.submit, resubmit=args.resubmit, fetch_inputs=args.fetch_inputs))})
    return 0
