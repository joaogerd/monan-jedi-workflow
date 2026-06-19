"""Regression test for the committed minimal cyclic experiment example."""

from pathlib import Path

from monan_jedi_workflow.cycle_plan import plan_cycle


EXPERIMENT = (
    Path(__file__).resolve().parents[1]
    / "configs/experiments/cycle_1day_3dfgat_x1.10242.yaml"
)


def test_committed_one_day_example_resolves_expected_trajectory() -> None:
    output = plan_cycle(EXPERIMENT)

    assert output.startswith("cycles: 4\n")
    assert "cycle: 2018041500" in output
    assert "cycle: 2018041518" in output
    assert "forecast_start: 2018-04-14T18:00:00Z" in output
    assert "forecast_end: 2018-04-15T03:00:00Z" in output
    assert "valid=2018-04-15T21:00:00Z offset_hours=3 lead_hours=9" in output
