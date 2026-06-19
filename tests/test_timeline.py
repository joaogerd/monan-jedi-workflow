"""Tests for pure cycle timeline resolution."""

from datetime import timedelta

import pytest

from monan_jedi_workflow.timeline import (
    CycleDefinition,
    format_cycle_id,
    format_mpas_timestamp,
    parse_utc_datetime,
    resolve_cycle_instances,
)


def gsi_style_definition(*, end: str = "2018-04-15T06:00:00Z") -> CycleDefinition:
    """Create the familiar 6-hour cycle with a [-3, 0, +3] FGAT trajectory."""
    return CycleDefinition.from_mapping(
        {
            "start": "2018-04-15T00:00:00Z",
            "end": end,
            "interval_hours": 6,
        },
        trajectory_offsets_hours=[-3, 0, 3],
    )


def test_gsi_style_fgat_trajectory_for_2018041500() -> None:
    """A 00Z analysis uses 3 h, 6 h and 9 h forecasts from the prior 18Z analysis."""
    [instance] = resolve_cycle_instances(gsi_style_definition())

    assert instance.cycle_id == "2018041500"
    assert instance.forecast_start_time == parse_utc_datetime("2018-04-14T18:00:00Z")
    assert instance.forecast_end_time == parse_utc_datetime("2018-04-15T03:00:00Z")
    assert instance.forecast_length == timedelta(hours=9)
    assert [state.valid_time for state in instance.trajectory] == [
        parse_utc_datetime("2018-04-14T21:00:00Z"),
        parse_utc_datetime("2018-04-15T00:00:00Z"),
        parse_utc_datetime("2018-04-15T03:00:00Z"),
    ]
    assert [state.forecast_lead for state in instance.trajectory] == [
        timedelta(hours=3),
        timedelta(hours=6),
        timedelta(hours=9),
    ]
    assert instance.window_begin == parse_utc_datetime("2018-04-14T21:00:00Z")
    assert instance.window_end == parse_utc_datetime("2018-04-15T03:00:00Z")
    assert format_mpas_timestamp(instance.background_time) == "2018-04-14_21.00.00"


def test_one_day_has_four_six_hour_analysis_cycles() -> None:
    instances = resolve_cycle_instances(
        gsi_style_definition(end="2018-04-16T00:00:00Z")
    )

    assert [item.cycle_id for item in instances] == [
        "2018041500",
        "2018041506",
        "2018041512",
        "2018041518",
    ]
    assert instances[1].forecast_start_time == parse_utc_datetime("2018-04-15T00:00:00Z")
    assert [state.valid_time for state in instances[1].trajectory] == [
        parse_utc_datetime("2018-04-15T03:00:00Z"),
        parse_utc_datetime("2018-04-15T06:00:00Z"),
        parse_utc_datetime("2018-04-15T09:00:00Z"),
    ]


def test_cycle_end_is_exclusive() -> None:
    definition = CycleDefinition(
        start=parse_utc_datetime("2018-04-15T00:00:00Z"),
        end=parse_utc_datetime("2018-04-15T06:00:00Z"),
        interval=timedelta(hours=6),
        trajectory_offsets=(
            timedelta(hours=-3),
            timedelta(hours=0),
            timedelta(hours=3),
        ),
    )

    assert [item.cycle_id for item in resolve_cycle_instances(definition)] == ["2018041500"]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("2018-04-15T00:00:00", "timezone"),
        ("not-a-datetime", "Invalid isoformat string"),
    ],
)
def test_parse_utc_datetime_rejects_invalid_values(value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_utc_datetime(value)


def test_cycle_definition_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="later"):
        CycleDefinition(
            start=parse_utc_datetime("2018-04-15T06:00:00Z"),
            end=parse_utc_datetime("2018-04-15T00:00:00Z"),
            interval=timedelta(hours=6),
            trajectory_offsets=(timedelta(hours=-3),),
        )


def test_cycle_definition_rejects_unsorted_trajectory_offsets() -> None:
    with pytest.raises(ValueError, match="ordered"):
        CycleDefinition(
            start=parse_utc_datetime("2018-04-15T00:00:00Z"),
            end=parse_utc_datetime("2018-04-15T06:00:00Z"),
            interval=timedelta(hours=6),
            trajectory_offsets=(timedelta(hours=0), timedelta(hours=-3)),
        )


def test_format_cycle_id() -> None:
    assert format_cycle_id(parse_utc_datetime("2018-04-15T00:00:00Z")) == "2018041500"
