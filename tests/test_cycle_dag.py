from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.cycle_dag import (
    build_cycle_dag,
    build_cycle_dag_from_experiment,
    format_cycle_dag,
)
from monan_jedi_workflow.cycle_plan import load_cycle_plan_definition
from monan_jedi_workflow.timeline import resolve_cycle_instances


EXPERIMENT = (
    Path(__file__).resolve().parents[1]
    / "configs/experiments/cycle_1day_3dfgat_x1.10242.yaml"
)


def test_cycle_dag_orders_core_tasks_and_links_cycles() -> None:
    instances = resolve_cycle_instances(load_cycle_plan_definition(EXPERIMENT))
    dag = build_cycle_dag(instances)

    assert dag.task_names()[:5] == [
        "prepare.2018041500",
        "observations.2018041500",
        "background.2018041500",
        "assimilate.2018041500",
        "forecast.2018041500",
    ]
    first_background = dag.tasks[2]
    second_background = dag.tasks[7]
    assert first_background.external_input is True
    assert first_background.depends_on == ("prepare.2018041500",)
    assert second_background.external_input is False
    assert second_background.depends_on == (
        "prepare.2018041506",
        "forecast.2018041500",
    )


def test_cycle_dag_adds_optional_diagnostics_as_sidecars() -> None:
    instances = resolve_cycle_instances(load_cycle_plan_definition(EXPERIMENT))[:1]

    dag = build_cycle_dag(instances, include_diagnostics=True)

    assert dag.task_names() == [
        "prepare.2018041500",
        "observations.2018041500",
        "background.2018041500",
        "assimilate.2018041500",
        "forecast.2018041500",
        "diagnostics_analysis.2018041500",
        "diagnostics_forecast.2018041500",
    ]
    assert dag.tasks[-2].depends_on == ("assimilate.2018041500",)
    assert dag.tasks[-1].depends_on == ("forecast.2018041500",)


def test_build_cycle_dag_from_experiment_uses_committed_example() -> None:
    dag = build_cycle_dag_from_experiment(EXPERIMENT)

    assert len(dag.tasks) == 20
    assert dag.tasks[-1].name == "forecast.2018041518"


def test_format_cycle_dag_is_stable_and_explicit() -> None:
    dag = build_cycle_dag_from_experiment(EXPERIMENT)
    text = format_cycle_dag(dag)

    assert "tasks: 20" in text
    assert "background.2018041500" in text
    assert "external_input=true" in text
