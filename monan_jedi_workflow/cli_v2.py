"""V2 command-line entry points."""

from __future__ import annotations

import argparse
from pathlib import Path

from .components.bmatrix.nmc_pairs.stage import NmcPairsStage
from .core.config import resolve_configuration, write_resolved_configuration
from .core.stage import RunContext
from .core.workflow_spec import WorkflowSpec
from .orchestration.local import LocalWorkflowRunner


def main(argv: list[str] | None = None) -> int:
    """Run a V2 workflow command.

    Parameters
    ----------
    argv : list[str] | None, default=None
        Command arguments excluding the executable name.

    Returns
    -------
    int
        Process exit status.
    """
    parser = argparse.ArgumentParser(prog="monan-jedi-workflow-v2")
    commands = parser.add_subparsers(dest="command", required=True)
    nmc = commands.add_parser("nmc-pairs", help="Validate NMC pairs and write a BFLOW manifest.")
    nmc.add_argument("--config", action="append", type=Path, required=True)
    nmc.add_argument("--workspace", type=Path, required=True)
    nmc.add_argument("--dry-run", action="store_true")
    nmc.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    config = resolve_configuration(args.config)
    case = config.get("case")
    if not isinstance(case, dict) or not isinstance(case.get("name"), str) or not case["name"]:
        parser.error("case.name must be a non-empty string")
    workspace = args.workspace.resolve()
    write_resolved_configuration(workspace / ".monan-jedi-workflow" / "resolved-config.yaml", config)
    context = RunContext("bmatrix", case["name"], workspace, config=config, dry_run=args.dry_run)
    stage = NmcPairsStage.from_context(context)
    specification = WorkflowSpec.from_stages("bmatrix", [stage.spec])
    results = LocalWorkflowRunner(specification, {stage.spec.name: stage}).run(context, force=args.force)
    for result in results:
        print(result.message)
    return 0
