"""Render V2 workflow specifications as simpleWorkflow task definitions."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from ...core.workflow_spec import StageSpec, WorkflowSpec


StageArgvFactory = Callable[[StageSpec], Sequence[str]]


def render_workflow(
    specification: WorkflowSpec,
    *,
    context: Mapping[str, str],
    argv_for_stage: StageArgvFactory,
) -> dict[str, Any]:
    """Render a scheduler-neutral workflow as a simpleWorkflow mapping.

    Parameters
    ----------
    specification : WorkflowSpec
        Scientific dependency graph to render.
    context : Mapping[str, str]
        Values exposed to simpleWorkflow placeholder expansion.
    argv_for_stage : StageArgvFactory
        Callback that produces an explicit process argument vector for each
        stage. The adapter never assembles shell command strings.

    Returns
    -------
    dict[str, Any]
        Mapping that conforms to the simpleWorkflow YAML task format.

    Raises
    ------
    ValueError
        Raised when the callback returns an empty argument vector.

    Notes
    -----
    The adapter preserves the original stage names and `needs` relationships as
    simpleWorkflow `name` and `depends_on` fields. This keeps the scientific DAG
    independent of the choice of orchestration backend.
    """
    tasks: list[dict[str, Any]] = []
    for name in specification.topological_order():
        stage = specification.stage(name)
        argv = list(argv_for_stage(stage))
        if not argv:
            raise ValueError(f"Stage '{stage.name}' rendered an empty argv vector.")
        task: dict[str, Any] = {"name": stage.name, "argv": argv}
        if stage.needs:
            task["depends_on"] = list(stage.needs)
        tasks.append(task)

    return {
        "workflow": {"name": specification.name},
        "context": dict(context),
        "tasks": tasks,
    }


def write_workflow(
    path: Path,
    specification: WorkflowSpec,
    *,
    context: Mapping[str, str],
    argv_for_stage: StageArgvFactory,
) -> Path:
    """Render and write one simpleWorkflow YAML definition.

    Parameters
    ----------
    path : Path
        Destination YAML file.
    specification : WorkflowSpec
        Scientific dependency graph to render.
    context : Mapping[str, str]
        Values exposed to simpleWorkflow placeholder expansion.
    argv_for_stage : StageArgvFactory
        Callback that produces explicit stage argument vectors.

    Returns
    -------
    Path
        Written YAML path.
    """
    payload = render_workflow(specification, context=context, argv_for_stage=argv_for_stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    # safe_dump keeps the generated definition inspectable and avoids emitting
    # Python-specific YAML tags into a file that simpleWorkflow must parse.
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path
