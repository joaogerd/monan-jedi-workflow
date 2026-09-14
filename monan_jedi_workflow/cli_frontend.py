"""User-facing MONAN-JEDI command line with campaign data acquisition."""

from __future__ import annotations

import sys
from pathlib import Path

from . import cli_extended
from .campaign import load_campaign_spec
from .corrected_campaign import _cycles, _iso
from .obs_acquisition import acquire_campaign_observations
from .obs_cycle_inputs import ObservationInputError
from .obs_cycle_stage import (
    check_obs_cycle_sources,
    doctor_obs2ioda_resolved,
    prepare_obs2ioda_resolved,
    run_obs2ioda_resolved,
)
from .stage_config import StageConfigurationError


def _error(message: str) -> str:
    return f"MONAN-JEDI workflow stopped\n{message}"


def _check_observations(config: Path) -> None:
    spec = load_campaign_spec(config)
    cycles = _cycles(spec.start_cycle, spec.end_cycle)[1:]
    resolved = 0
    for cycle in cycles:
        resolved += len(check_obs_cycle_sources(spec.obs2ioda_config.parent, _iso(cycle)))
    suffix = f"; {resolved} dated path(s) resolved by cycle" if resolved else ""
    print(f"  [OK  ] observation cycle consistency: {len(cycles)} cycles{suffix}")


def _fetch_observations(config: Path) -> None:
    print("Observation acquisition")
    records = acquire_campaign_observations(config)
    remote_count = 0
    local_count = 0
    for record in records:
        method = getattr(record, "method", "")
        target = getattr(record, "resolved", None) or getattr(record, "destination", None)
        cycle = getattr(record, "cycle", "")
        converter = getattr(record, "converter", "")
        if method.startswith("https"):
            remote_count += 1
            source = getattr(record, "source", "")
            print(f"  [FETCH] {cycle} {converter}")
            print(f"          {source}")
            print(f"       -> {target}")
        else:
            local_count += 1
            print(f"  [LOCAL] {cycle} {converter}: {target}")
    if not records:
        print("  [OK  ] all required observation inputs already available")
    else:
        print(f"  [OK  ] acquisition complete: {remote_count} fetched, {local_count} resolved locally")


def _dispatch(args: list[str]) -> int:
    if args and args[0] in {"obs2ioda-doctor", "obs2ioda-prepare", "obs2ioda-run"}:
        cycle_index = args.index("--cycle")
        cycle = args[cycle_index + 1]
        config_dir = Path(args[1])
        if args[0] == "obs2ioda-doctor":
            doctor_obs2ioda_resolved(config_dir, cycle)
        elif args[0] == "obs2ioda-prepare":
            prepare_obs2ioda_resolved(config_dir, cycle, refresh="--refresh" in args)
        else:
            run_obs2ioda_resolved(config_dir, cycle, force="--force" in args)
        return 0

    if len(args) >= 3 and args[0] == "campaign":
        action = args[1]
        config = Path(args[2])
        if action == "fetch":
            _fetch_observations(config)
            _check_observations(config)
            return 0
        if action in {"create", "run"}:
            _fetch_observations(config)
            _check_observations(config)
        elif action == "check":
            _check_observations(config)

    return cli_extended.main(args)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return _dispatch(args)
    except (ObservationInputError, StageConfigurationError, FileNotFoundError) as error:
        print(_error(str(error)), file=sys.stderr)
        return 2
    except RuntimeError as error:
        if args and (args[0].startswith("obs2ioda-") or args[0] == "campaign"):
            print(_error(str(error)), file=sys.stderr)
            return 2
        raise
