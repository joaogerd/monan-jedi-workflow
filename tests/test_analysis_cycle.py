import pytest

from monan_jedi_workflow.analysis_cycle import analysis_cycle_context
from monan_jedi_workflow.cycle_context import parse_cycle_time
from monan_jedi_workflow.stage_config import StageConfigurationError


def test_reference_fgat_time_context() -> None:
    context = analysis_cycle_context(
        parse_cycle_time("2018-04-15T00:00:00Z"),
        step_hours=6,
        background_offset_hours=-3,
        window_hours=6,
    )

    assert context["analysis_yyyymmddhh"] == "2018041500"
    assert context["background_yyyymmddhh"] == "2018041421"
    assert context["previous_cycle_yyyymmddhh"] == "2018041418"
    assert context["next_cycle_yyyymmddhh"] == "2018041506"
    assert context["next_background_yyyymmddhh"] == "2018041503"
    assert context["window_begin_time"] == "2018-04-14T21:00:00Z"
    assert context["window_end_time"] == "2018-04-15T03:00:00Z"
    assert context["window_length"] == "PT6H"


def test_cycle_step_does_not_define_background_offset() -> None:
    context = analysis_cycle_context(
        parse_cycle_time("2018-04-15T00:00:00Z"),
        step_hours=12,
        background_offset_hours=-3,
        window_hours=6,
    )

    assert context["previous_cycle_yyyymmddhh"] == "2018041412"
    assert context["background_yyyymmddhh"] == "2018041421"


def test_invalid_cycle_durations_fail_early() -> None:
    with pytest.raises(StageConfigurationError, match="step_hours"):
        analysis_cycle_context(
            parse_cycle_time("2018-04-15T00:00:00Z"),
            step_hours=0,
            background_offset_hours=-3,
            window_hours=6,
        )
