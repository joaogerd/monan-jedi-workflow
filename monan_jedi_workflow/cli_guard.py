"""User-facing CLI guard for cycle-safe observation commands."""

from __future__ import annotations

import sys
from pathlib import Path

from . import cli_extended
from .obs_cycle_inputs import ObservationInputError
from .obs_cycle_stage import (
    doctor_obs2ioda_resolved,
    prepare_obs2ioda_resolved,
    run_obs2ioda_resolved,
)
from .stage_config import StageConfigurationError


def format_error(message: str) -> str:
    return f"MONAN-JEDI workflow stopped\n{message}"


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
    return cli_extended.main(args)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return _dispatch(args)
    except (ObservationInputError, StageConfigurationError, FileNotFoundError) as error:
        print(format_error(str(error)), file=sys.stderr)
        return 2
