"""V2 command-line entry points."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .components.bmatrix.nmc_pairs.stage import NmcPairsStage
from .core.config import ConfigurationError, resolve_configuration, write_resolved_configuration
from .core.provenance import RunProvenance, default_environment_facts, write_provenance
from .core.stage import RunContext
from .core.workflow_spec import WorkflowSpec
from .orchestration.local import LocalWorkflowRunner
from .platforms.local import LocalProcessBackend
from .workflows.nmc_campaign import build_nmc_campaign


def _case_name(config: dict[str, object]) -> str:
    """Extract the required `case.name` value from resolved configuration."""
    case = config.get("case")
    if not isinstance(case, dict) or not isinstance(case.get("name"), str) or not case["name"]:
        raise ConfigurationError("case.name must be a non-empty string.")
    return case["name"]


def _context(config_paths: Sequence[Path], workspace: Path, *, dry_run: bool, argv: Sequence[str]) -> RunContext:
    """Resolve configuration and persist reproducibility metadata for one run."""
    config = resolve_configuration(list(config_paths))
    case = _case_name(config)
    workspace = workspace.resolve()
    metadata = workspace / ".monan-jedi-workflow"
    resolved = write_resolved_configuration(metadata / "resolved-config.yaml", config)
    write_provenance(
        metadata / "provenance.json",
        RunProvenance(
            workflow="bmatrix",
            case=case,
            command=tuple(argv),
            code_revision=None,
            resolved_config=resolved,
            environment=default_environment_facts(),
        ),
    )
    return RunContext("bmatrix", case, workspace, config=config, dry_run=dry_run)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared case, workspace, dry-run, and restart options."""
    parser.add_argument("--config", action="append", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")


def main(argv: Sequence[str] | None = None) -> int:
    """Run a V2 workflow command.

    Parameters
    ----------
    argv : Sequence[str] | None, default=None
        Command arguments excluding the executable name.

    Returns
    -------
    int
        Process exit status.
    """
    values = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="monan-jedi-workflow-v2")
    commands = parser.add_subparsers(dest="command", required=True)
    nmc = commands.add_parser("nmc-pairs", help="Validate NMC pairs and write a BFLOW manifest.")
    _add_common_arguments(nmc)
    campaign = commands.add_parser(
        "nmc-campaign",
        help="Run or plan MPAS initialization, forecasts, and NMC manifest publication locally.",
    )
    _add_common_arguments(campaign)
    args = parser.parse_args(values)
    context = _context(args.config, args.workspace, dry_run=args.dry_run, argv=("monan-jedi-workflow-v2", *values))

    if args.command == "nmc-pairs":
        stage = NmcPairsStage.from_context(context)
        specification = WorkflowSpec.from_stages("bmatrix", [stage.spec])
        runner = LocalWorkflowRunner(specification, {stage.spec.name: stage})
    elif args.command == "nmc-campaign":
        plan = build_nmc_campaign(context, backend=LocalProcessBackend())
        runner = LocalWorkflowRunner(plan.specification, plan.stages)
    else:
        raise AssertionError(f"Unhandled V2 command: {args.command}")

    for result in runner.run(context, force=args.force):
        print(result.message)
    return 0
