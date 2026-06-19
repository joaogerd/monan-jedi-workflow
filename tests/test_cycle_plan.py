"""Tests for the non-mutating cycle planning interface."""

from pathlib import Path

import pytest

from monan_jedi_workflow.cycle_plan import format_cycle_plan, load_cycle_plan_definition, plan_cycle
from monan_jedi_workflow.timeline import resolve_cycle_instances


def write_experiment(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_plan_one_gsi_style_cycle(tmp_path: Path) -> None:
    experiment = write_experiment(
        tmp_path / "experiment.yaml",
        """
cycle:
  start: 2018-04-15T00:00:00Z
  end: 2018-04-15T06:00:00Z
  interval_hours: 6
assimilation:
  method: 3dvar_fgat
  fgat:
    trajectory_offsets_hours: [-3, 0, 3]
""",
    )

    output = plan_cycle(experiment)

    assert "cycles: 1" in output
    assert "cycle: 2018041500" in output
    assert "forecast_start: 2018-04-14T18:00:00Z" in output
    assert "forecast_end: 2018-04-15T03:00:00Z" in output
    assert "offset_hours=-3 lead_hours=3" in output
    assert "offset_hours=0 lead_hours=6" in output
    assert "offset_hours=3 lead_hours=9" in output
    assert list(tmp_path.iterdir()) == [experiment]


def test_plan_one_day_has_four_cycles(tmp_path: Path) -> None:
    experiment = write_experiment(
        tmp_path / "experiment.yaml",
        """
cycle:
  start: 2018-04-15T00:00:00Z
  end: 2018-04-16T00:00:00Z
  interval_hours: 6
assimilation:
  method: 3dvar_fgat
  fgat:
    trajectory_offsets_hours: [-3, 0, 3]
""",
    )

    definition = load_cycle_plan_definition(experiment)
    instances = resolve_cycle_instances(definition)

    assert [item.cycle_id for item in instances] == [
        "2018041500",
        "2018041506",
        "2018041512",
        "2018041518",
    ]
    assert "forecast_start: 2018-04-15T00:00:00Z" in format_cycle_plan(instances)


@pytest.mark.parametrize(
    ("content", "exception", "message"),
    [
        (
            "cycle: {}\nassimilation: {method: 3dvar}\n",
            ValueError,
            "3dvar_fgat",
        ),
        (
            "cycle: {}\nassimilation: {method: 3dvar_fgat}\n",
            KeyError,
            "assimilation.fgat",
        ),
        (
            "cycle: {}\nassimilation: {method: 3dvar_fgat, fgat: {trajectory_offsets_hours: [-3, bad, 3]}}\n",
            TypeError,
            "list of integers",
        ),
    ],
)
def test_plan_rejects_invalid_configuration(
    tmp_path: Path, content: str, exception: type[Exception], message: str
) -> None:
    experiment = write_experiment(tmp_path / "experiment.yaml", content)

    with pytest.raises(exception, match=message):
        load_cycle_plan_definition(experiment)
