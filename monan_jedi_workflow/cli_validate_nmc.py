"""Audit existing V2 NMC campaign artifacts without submitting jobs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .cli_v2 import _campaign_plan, _context
from .workflows.nmc_validation import validate_nmc_campaign, write_nmc_campaign_validation


def main(argv: Sequence[str] | None = None) -> int:
    """Validate an existing NMC campaign and write one JSON audit record."""
    values = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="monan-jedi-workflow-v2-validate-nmc")
    parser.add_argument("--config", action="append", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--backend", choices=("local", "jaci-pbs"), default="local")
    args = parser.parse_args(values)
    context = _context(args.config, args.workspace, dry_run=False, argv=("monan-jedi-workflow-v2-validate-nmc", *values))
    plan = _campaign_plan(context, args.backend)
    validation = validate_nmc_campaign(plan, context)
    path = write_nmc_campaign_validation(
        context.workspace / ".monan-jedi-workflow" / "validation" / "nmc-campaign.json",
        validation,
    )
    print(path)
    return 0 if validation.is_valid else 2
