"""Tests for cyclic dry-run reporting."""

from pathlib import Path

from monan_jedi_workflow.dry_run import dry_run_experiment, planned_cycle_artifacts
from monan_jedi_workflow.timeline import CycleDefinition, resolve_cycle_instances


EXPERIMENT = (
    Path(__file__).resolve().parents[1]
    / "configs/experiments/cycle_1day_3dfgat_x1.10242.yaml"
)


def test_dry_run_reports_components_cycles_tasks_and_artifacts() -> None:
    output = dry_run_experiment(EXPERIMENT)

    assert output.startswith("dry-run: no files will be created\n")
    assert "dry-run: no jobs will be submitted" in output
    assert "[OK] components resolved" in output
    assert "assimilation: 3dvar_fgat" in output
    assert "forecast: mpas_fgat_3h" in output
    assert "bmatrix: mpasstatic_x1.10242" in output
    assert "planned cycles: 4" in output
    assert "[PLAN] cycle 2018041500" in output
    assert "trajectory forecast: 2018-04-14T18:00:00Z -> 2018-04-15T03:00:00Z" in output
    assert "offset=-3h lead=3h" in output
    assert "1. resolve trajectory inputs" in output
    assert "runs/cycle_1day_3dfgat_x1.10242/2018041500/assimilation/3dvar_fgat.yaml" in output
    assert "[PLAN] cycle 2018041518" in output


def test_dry_run_does_not_create_files(tmp_path: Path) -> None:
    before = sorted(path.name for path in tmp_path.iterdir())

    output = dry_run_experiment(EXPERIMENT)

    assert output
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_planned_artifacts_are_scoped_to_cycle_runtime() -> None:
    definition = CycleDefinition.from_mapping(
        {
            "start": "2018-04-15T00:00:00Z",
            "end": "2018-04-15T06:00:00Z",
            "interval_hours": 6,
        },
        trajectory_offsets_hours=[-3, 0, 3],
    )
    [instance] = resolve_cycle_instances(definition)

    artifacts = planned_cycle_artifacts("example", instance)

    assert all(item.startswith("runs/example/2018041500/") for item in artifacts)
    assert artifacts[-1].endswith("forecast/run_forecast.pbs")
