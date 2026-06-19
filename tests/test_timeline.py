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


def test_baseline_fgat_time_resolution() -> None:
    """The historical 2018041500 baseline resolves to its known 21Z background."""
    definition = CycleDefinition.from_mapping(
        {
            "start": "2018-04-15T00:00:00Z",
            "end": "2018-04-15T06:00:00Z",
            "interval_hours": 6,
        },
        background_offset_hours=-3,
        window_length_hours=6,
    )

    [instance] = resolve_cycle_instances(definition)

    assert instance.cycle_id == "2018041500"
    assert format_mpas_timestamp(instance.background_time) == "2018-04-14_21.00.00"
    assert instance.window_begin == instance.background_time
    assert instance.window_end == parse_utc_datetime("2018-04-15T03:00:00Z")


def test_one_day_has_four_six_hour_analysis_cycles() -> None:
    definition = CycleDefinition.from_mapping(
        {
            "start": "2018-04-15T00:00:00Z",
            "end": "2018-04-16T00:00:00Z",
            "interval_hours": 6,
        },
        background_offset_hours=-3,
        window_length_hours=6,
    )

    instances = resolve_cycle_instances(definition)

    assert [item.cycle_id for item in instances] == [
        "2018041500",
        "2018041506",
        "2018041512",
        "2018041518",
    ]
    assert instances[1].background_time == parse_utc_datetime("2018-04-15T03:00:00Z")


def test_cycle_end_is_exclusive() -> None:
    definition = CycleDefinition(
        start=parse_utc_datetime("2018-04-15T00:00:00Z"),
        end=parse_utc_datetime("2018-04-15T06:00:00Z"),
        interval=timedelta(hours=6),
        background_offset=timedelta(hours=-3),
        window_length=timedelta(hours=6),
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
            background_offset=timedelta(hours=-3),
            window_length=timedelta(hours=6),
        )


def test_format_cycle_id() -> None:
    assert format_cycle_id(parse_utc_datetime("2018-04-15T00:00:00Z")) == "2018041500"
