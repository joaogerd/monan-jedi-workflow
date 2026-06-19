"""Plan a cyclic experiment without creating files or submitting jobs.

The dry run is intentionally a pure read-only operation. It combines the
minimal experiment, selected component defaults and the FGAT timeline, then
reports the runtime artifacts and tasks that a future prepare command would
create.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .composition import compose_cyclic_experiment
from .cycle_plan import load_cycle_plan_definition
from .timeline import CycleInstance, resolve_cycle_instances


def _utc(value: object) -> str:
    return str(value).replace("+00:00", "Z")


def planned_cycle_artifacts(experiment_name: str, instance: CycleInstance) -> list[str]:
    """Return relative paths that a future prepare command would create."""
    root = f"runs/{experiment_name}/{instance.cycle_id}"
    return [
        f"{root}/manifest.yaml",
        f"{root}/resolved-config.yaml",
        f"{root}/assimilation/3dvar_fgat.yaml",
        f"{root}/assimilation/run_assimilation.pbs",
        f"{root}/forecast/namelist.atmosphere",
        f"{root}/forecast/streams.atmosphere",
        f"{root}/forecast/run_forecast.pbs",
    ]


def planned_cycle_tasks(instance: CycleInstance) -> list[str]:
    """Return the ordered non-executing task plan for one analysis cycle."""
    return [
        "resolve trajectory inputs",
        "validate trajectory products",
        "render MPAS forecast inputs",
        "render MPAS-JEDI 3DVar-FGAT YAML",
        "render forecast PBS",
        "render assimilation PBS",
        "validate rendered runtime",
    ]


def format_dry_run(effective: dict[str, Any], instances: list[CycleInstance]) -> str:
    """Render a stable human-readable dry-run report."""
    name = str(effective["experiment"].get("name", "unnamed-experiment"))
    lines = [
        "dry-run: no files will be created",
        "dry-run: no jobs will be submitted",
        "",
        "[OK] components resolved",
        f"  assimilation: {effective['assimilation']['method']}",
        f"  forecast: {effective['forecast']['profile']}",
        f"  background: {effective['background']['source']}",
        f"  bmatrix: {effective['bmatrix']['name']}",
        f"  observations: {effective['observations']['set']}",
        f"  geometry: {effective['geometry']['name']}",
        f"  platform: {effective['platform']['name']}",
        f"  tasks: {effective['run']['tasks']}",
        "",
        f"planned cycles: {len(instances)}",
    ]

    for instance in instances:
        lines.extend(
            [
                "",
                f"[PLAN] cycle {instance.cycle_id}",
                f"  analysis: {_utc(instance.analysis_time.isoformat())}",
                f"  trajectory forecast: {_utc(instance.forecast_start_time.isoformat())} -> {_utc(instance.forecast_end_time.isoformat())}",
                f"  forecast length: {int(instance.forecast_length.total_seconds() // 3600)} h",
                "  required trajectory states:",
            ]
        )
        for state in instance.trajectory:
            lines.append(
                "    - "
                f"{_utc(state.valid_time.isoformat())} "
                f"offset={int(state.offset_from_analysis.total_seconds() // 3600)}h "
                f"lead={int(state.forecast_lead.total_seconds() // 3600)}h"
            )
        lines.append("  planned tasks:")
        for index, task in enumerate(planned_cycle_tasks(instance), start=1):
            lines.append(f"    {index}. {task}")
        lines.append("  planned artifacts:")
        for artifact in planned_cycle_artifacts(name, instance):
            lines.append(f"    - {artifact}")

    return "\n".join(lines)


def dry_run_experiment(experiment_path: Path) -> str:
    """Resolve and report a cyclic experiment without filesystem mutation."""
    effective = compose_cyclic_experiment(experiment_path)
    definition = load_cycle_plan_definition(experiment_path)
    return format_dry_run(effective, resolve_cycle_instances(definition))
