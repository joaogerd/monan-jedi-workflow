"""Build a declarative DAG for cyclic MONAN-JEDI experiments.

The DAG describes stage ordering only. It does not create runtime directories,
render files, execute MPAS/JEDI, invoke PBS or inspect the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cycle_plan import load_cycle_plan_definition
from .timeline import CycleInstance, resolve_cycle_instances

BASE_STAGES = ("prepare", "observations", "background", "assimilate", "forecast")
OPTIONAL_DIAGNOSTIC_STAGES = ("diagnostics_analysis", "diagnostics_forecast")


@dataclass(frozen=True)
class CycleTask:
    """One declarative task in a cyclic experiment DAG."""

    name: str
    cycle_id: str
    stage: str
    depends_on: tuple[str, ...]
    external_input: bool = False


@dataclass(frozen=True)
class CycleDag:
    """A deterministic set of cyclic workflow tasks."""

    tasks: tuple[CycleTask, ...]

    def task_names(self) -> list[str]:
        """Return task names in deterministic execution order."""
        return [task.name for task in self.tasks]


def _task_name(stage: str, cycle_id: str) -> str:
    return f"{stage}.{cycle_id}"


def _build_cycle_tasks(
    instance: CycleInstance,
    *,
    previous_cycle: CycleInstance | None,
    include_diagnostics: bool,
) -> list[CycleTask]:
    cycle_id = instance.cycle_id
    prepare = _task_name("prepare", cycle_id)
    observations = _task_name("observations", cycle_id)
    background = _task_name("background", cycle_id)
    assimilate = _task_name("assimilate", cycle_id)
    forecast = _task_name("forecast", cycle_id)

    background_dependencies = [prepare]
    external_input = previous_cycle is None
    if previous_cycle is not None:
        background_dependencies.append(_task_name("forecast", previous_cycle.cycle_id))

    tasks = [
        CycleTask(prepare, cycle_id, "prepare", ()),
        CycleTask(observations, cycle_id, "observations", (prepare,)),
        CycleTask(
            background,
            cycle_id,
            "background",
            tuple(background_dependencies),
            external_input=external_input,
        ),
        CycleTask(assimilate, cycle_id, "assimilate", (observations, background)),
        CycleTask(forecast, cycle_id, "forecast", (assimilate,)),
    ]

    if include_diagnostics:
        tasks.extend(
            [
                CycleTask(
                    _task_name("diagnostics_analysis", cycle_id),
                    cycle_id,
                    "diagnostics_analysis",
                    (assimilate,),
                ),
                CycleTask(
                    _task_name("diagnostics_forecast", cycle_id),
                    cycle_id,
                    "diagnostics_forecast",
                    (forecast,),
                ),
            ]
        )

    return tasks


def build_cycle_dag(
    instances: list[CycleInstance],
    *,
    include_diagnostics: bool = False,
) -> CycleDag:
    """Build task dependencies for resolved cycle instances."""
    tasks: list[CycleTask] = []
    previous: CycleInstance | None = None
    for instance in instances:
        tasks.extend(
            _build_cycle_tasks(
                instance,
                previous_cycle=previous,
                include_diagnostics=include_diagnostics,
            )
        )
        previous = instance
    return CycleDag(tuple(tasks))


def build_cycle_dag_from_experiment(
    experiment_path: Path,
    *,
    include_diagnostics: bool = False,
) -> CycleDag:
    """Load an experiment file and build its side-effect-free task DAG."""
    definition = load_cycle_plan_definition(experiment_path)
    instances = resolve_cycle_instances(definition)
    return build_cycle_dag(instances, include_diagnostics=include_diagnostics)


def format_cycle_dag(dag: CycleDag) -> str:
    """Format a DAG as stable human-readable text."""
    lines = [f"tasks: {len(dag.tasks)}"]
    for task in dag.tasks:
        deps = ", ".join(task.depends_on) if task.depends_on else "none"
        suffix = " external_input=true" if task.external_input else ""
        lines.append(f"- {task.name}: stage={task.stage} depends_on={deps}{suffix}")
    return "\n".join(lines)
