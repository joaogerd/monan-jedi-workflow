"""V2 command-line entry points."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Sequence

from .components.bmatrix.nmc_pairs.stage import NmcPairsStage
from .core.config import ConfigurationError, resolve_configuration, write_resolved_configuration
from .core.provenance import RunProvenance, default_environment_facts, write_provenance
from .core.stage import RunContext
from .core.workflow_spec import WorkflowSpec, WorkflowSpecificationError
from .orchestration.local import LocalWorkflowRunner, StageTaskRunner
from .orchestration.simpleworkflow.adapter import write_workflow
from .platforms.jaci_config import jaci_backend_factory
from .platforms.local import LocalProcessBackend
from .workflows.nmc_campaign import NmcCampaignPlan, build_nmc_campaign


def _case_name(config: dict[str, object]) -> str:
    """Extract the required `case.name` value from resolved configuration."""
    case = config.get("case")
    if not isinstance(case, dict) or not isinstance(case.get("name"), str) or not case["name"]:
        raise ConfigurationError("case.name must be a non-empty string.")
    return case["name"]


def _context(
    config_paths: Sequence[Path],
    workspace: Path,
    *,
    dry_run: bool,
    prepare_only: bool,
    argv: Sequence[str],
) -> RunContext:
    """Resolve configuration and persist run plus command-level provenance."""
    config = resolve_configuration(list(config_paths))
    case = _case_name(config)
    workspace = workspace.resolve()
    metadata = workspace / ".monan-jedi-workflow"
    resolved = write_resolved_configuration(metadata / "resolved-config.yaml", config)
    provenance = RunProvenance(
        workflow="bmatrix",
        case=case,
        command=tuple(argv),
        code_revision=None,
        resolved_config=resolved,
        environment=default_environment_facts(),
    )
    write_provenance(metadata / "provenance.json", provenance)
    digest = hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()[:16]
    write_provenance(metadata / "provenance" / f"command-{digest}.json", provenance)
    return RunContext("bmatrix", case, workspace, config=config, dry_run=dry_run, prepare_only=prepare_only)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared case, workspace, dry-run, and restart options."""
    parser.add_argument("--config", action="append", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")


def _campaign_plan(context: RunContext, backend_name: str) -> NmcCampaignPlan:
    """Build one NMC campaign with local or JACI execution backends."""
    if backend_name == "local":
        return build_nmc_campaign(context, backend=LocalProcessBackend())
    if backend_name == "jaci-pbs":
        return build_nmc_campaign(
            context,
            wps_backend_factory=jaci_backend_factory(context.config, stage_kind="wps"),
            initialization_backend_factory=jaci_backend_factory(context.config, stage_kind="initialization"),
            forecast_backend_factory=jaci_backend_factory(context.config, stage_kind="forecast"),
        )
    raise ValueError(f"Unsupported V2 backend: {backend_name}")


def _render_simpleworkflow(path: Path, plan: NmcCampaignPlan, context: RunContext, backend: str) -> Path:
    """Render one NMC campaign as simpleWorkflow tasks calling `stage run`."""
    output = path if path.is_absolute() else context.workspace / path
    resolved = context.workspace / ".monan-jedi-workflow" / "resolved-config.yaml"
    return write_workflow(
        output,
        plan.specification,
        context={
            "resolved_config": str(resolved),
            "workflow_workspace": str(context.workspace),
            "backend": backend,
        },
        argv_for_stage=lambda stage: (
            "monan-jedi-workflow-v2",
            "stage",
            "run",
            "--stage",
            stage.name,
            "--config",
            "{resolved_config}",
            "--workspace",
            "{workflow_workspace}",
            "--backend",
            "{backend}",
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run, plan, prepare, or render a V2 workflow.

    ``nmc-campaign --prepare-only`` validates static inputs and materializes
    links/templates without calling a model executable or scheduler command.
    """
    values = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="monan-jedi-workflow-v2")
    commands = parser.add_subparsers(dest="command", required=True)

    nmc = commands.add_parser("nmc-pairs", help="Validate NMC pairs and write a BFLOW manifest.")
    _add_common_arguments(nmc)

    campaign = commands.add_parser(
        "nmc-campaign",
        help="Run, plan, prepare, or render MPAS initialization, forecasts, and NMC publication.",
    )
    _add_common_arguments(campaign)
    campaign.add_argument("--backend", choices=("local", "jaci-pbs"), default="local")
    modes = campaign.add_mutually_exclusive_group()
    modes.add_argument(
        "--prepare-only",
        action="store_true",
        help="Validate static inputs and render links/templates without qsub or model execution.",
    )
    modes.add_argument(
        "--render-simpleworkflow",
        type=Path,
        help="Write simpleWorkflow YAML instead of executing the campaign.",
    )

    stage = commands.add_parser("stage", help="Run one declared V2 workflow stage.")
    stage_commands = stage.add_subparsers(dest="stage_command", required=True)
    stage_run = stage_commands.add_parser("run", help="Run one stage after validating dependency artifacts.")
    _add_common_arguments(stage_run)
    stage_run.add_argument("--stage", required=True, help="Stage name from the configured workflow specification.")
    stage_run.add_argument("--backend", choices=("local", "jaci-pbs"), default="local")

    args = parser.parse_args(values)
    prepare_only = bool(getattr(args, "prepare_only", False))
    if prepare_only and args.dry_run:
        parser.error("--prepare-only and --dry-run are mutually exclusive.")
    context = _context(
        args.config,
        args.workspace,
        dry_run=args.dry_run,
        prepare_only=prepare_only,
        argv=("monan-jedi-workflow-v2", *values),
    )

    if args.command == "nmc-pairs":
        selected = NmcPairsStage.from_context(context)
        runner = LocalWorkflowRunner(
            WorkflowSpec.from_stages("bmatrix", [selected.spec]),
            {selected.spec.name: selected},
        )
        results = runner.run(context, force=args.force)
    elif args.command == "nmc-campaign":
        plan = _campaign_plan(context, args.backend)
        if args.render_simpleworkflow:
            rendered = _render_simpleworkflow(args.render_simpleworkflow, plan, context, args.backend)
            print(rendered)
            return 0
        results = LocalWorkflowRunner(plan.specification, plan.stages).run(context, force=args.force)
    elif args.command == "stage" and args.stage_command == "run":
        plan = _campaign_plan(context, args.backend)
        try:
            result = StageTaskRunner(plan.specification, plan.stages).run(context, args.stage, force=args.force)
        except WorkflowSpecificationError as exc:
            parser.error(str(exc))
        results = () if result is None else (result,)
    else:
        raise AssertionError(f"Unhandled V2 command: {args.command}")

    for result in results:
        print(result.message)
    return 0
