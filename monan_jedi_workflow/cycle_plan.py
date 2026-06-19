"""Read and print a side-effect-free plan for a cyclic FGAT experiment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .timeline import CycleDefinition, CycleInstance, resolve_cycle_instances
from .yaml_utils import load_yaml_file


def load_cycle_plan_definition(path: Path) -> CycleDefinition:
    """Load the minimum fields required to plan a 3DVar-FGAT trajectory.

    This temporary planning contract deliberately reads only the experiment's
    cycle and assimilation sections. In the next composition phase, the FGAT
    settings will be supplied by the selected method component instead.
    """
    config = load_yaml_file(path)
    cycle = config.get("cycle")
    assimilation = config.get("assimilation")

    if not isinstance(cycle, dict):
        raise KeyError("Missing required mapping: cycle")
    if not isinstance(assimilation, dict):
        raise KeyError("Missing required mapping: assimilation")

    method = assimilation.get("method")
    if method != "3dvar_fgat":
        raise ValueError(
            "cycle plan currently supports assimilation.method: 3dvar_fgat"
        )

    fgat = assimilation.get("fgat")
    if not isinstance(fgat, dict):
        raise KeyError("Missing required mapping: assimilation.fgat")

    offsets = fgat.get("trajectory_offsets_hours")
    if not isinstance(offsets, list) or not all(isinstance(item, int) for item in offsets):
        raise TypeError(
            "assimilation.fgat.trajectory_offsets_hours must be a YAML list of integers"
        )

    origin = fgat.get("forecast_start_offset_hours")
    if origin is not None and not isinstance(origin, int):
        raise TypeError("assimilation.fgat.forecast_start_offset_hours must be an integer")

    return CycleDefinition.from_mapping(
        cycle,
        trajectory_offsets_hours=offsets,
        forecast_start_offset_hours=origin,
    )


def format_cycle_plan(instances: list[CycleInstance]) -> str:
    """Format resolved cycles as stable human-readable text without writing files."""
    lines = [f"cycles: {len(instances)}"]
    for instance in instances:
        lines.extend(
            [
                f"cycle: {instance.cycle_id}",
                f"  analysis: {instance.analysis_time.isoformat().replace('+00:00', 'Z')}",
                f"  forecast_start: {instance.forecast_start_time.isoformat().replace('+00:00', 'Z')}",
                f"  forecast_end: {instance.forecast_end_time.isoformat().replace('+00:00', 'Z')}",
                f"  forecast_length_hours: {int(instance.forecast_length.total_seconds() // 3600)}",
                "  trajectory:",
            ]
        )
        for state in instance.trajectory:
            lines.append(
                "    - "
                f"valid={state.valid_time.isoformat().replace('+00:00', 'Z')} "
                f"offset_hours={int(state.offset_from_analysis.total_seconds() // 3600)} "
                f"lead_hours={int(state.forecast_lead.total_seconds() // 3600)}"
            )
    return "\n".join(lines)


def plan_cycle(path: Path) -> str:
    """Resolve and format a cycle plan without filesystem side effects."""
    definition = load_cycle_plan_definition(path)
    return format_cycle_plan(resolve_cycle_instances(definition))
