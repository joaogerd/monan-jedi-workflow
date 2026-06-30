"""Research-facing CLI for high-level MPAS workflow planning."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .mpas_pipeline import (
    acquire_remote,
    build_plan,
    load_pipeline_run,
    reusable_state,
    resolve_inputs,
    resolve_static_assets,
    validate_contract,
    write_state,
)


def _report(value: dict) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _prepare(run, *, fetch: bool, force: bool) -> None:
    assets = resolve_inputs(run)
    paths = [acquire_remote(item, allow_download=fetch, force=force) for item in assets]
    if force or not reusable_state(run, "inputs"):
        write_state(run, "inputs", inputs=paths, outputs=paths, action="validated-or-acquired")
    statics = [path for _, path in resolve_static_assets(run)]
    if force or not reusable_state(run, "static"):
        write_state(run, "static", inputs=statics, outputs=statics, action="validated")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monan-jedi-mpas")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "plan", "status", "prepare", "prepare-bmatrix"):
        item = sub.add_parser(name)
        item.add_argument("config", type=Path)
        item.add_argument("--cycle", required=True, metavar="TIME")
        if name == "prepare":
            item.add_argument("--fetch", action="store_true")
            item.add_argument("--force", action="store_true")
            item.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run = load_pipeline_run(args.config, args.cycle)
    if args.command == "validate":
        _report(validate_contract(run))
        return 0
    if args.command == "plan":
        _report({"cycle_time": run.cycle.cycle_time, "stages": [item.__dict__ for item in build_plan(run)]})
        return 0
    if args.command == "status":
        _report({"cycle_time": run.cycle.cycle_time, "state_root": str(run.state_root), "stages": [{"name": item.name, "reusable": reusable_state(run, item.name)} for item in build_plan(run)]})
        return 0
    if args.command == "prepare":
        validate_contract(run, strict_inputs=not args.fetch)
        if args.dry_run:
            _report({"dry_run": True, "stages": [item.__dict__ for item in build_plan(run)]})
            return 0
        _prepare(run, fetch=args.fetch, force=args.force)
        print(f"[OK] prepared MPAS workflow inputs: {run.cycle.cycle_time}")
        return 0
    if args.command == "prepare-bmatrix":
        validate_contract(run)
        if not any(item.name == "bmatrix_samples" for item in build_plan(run)):
            raise ValueError("Set pipeline.stages.mode: bmatrix before preparing a B-matrix contract.")
        output = run.work_root / "bmatrix" / run.cycle.cycle_id / "sample-contract.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"cycle_time": run.cycle.cycle_time, "mesh": run.config.get("mpas", {}).get("mesh"), "purpose": "External B-matrix sample contract"}, indent=2) + "\n", encoding="utf-8")
        write_state(run, "bmatrix_samples", inputs=[], outputs=[output], action="prepared-contract")
        print(f"[OK] prepared B-matrix sample contract: {output}")
        return 0
    return 2
