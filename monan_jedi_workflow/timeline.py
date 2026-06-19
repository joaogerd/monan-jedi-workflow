"""Pure time-resolution utilities for cyclic MONAN-JEDI experiments.

This module intentionally has no filesystem, renderer, scheduler or PBS
side-effects.  It converts a declarative cycle definition into deterministic
analysis instances that later workflow layers can use to render runtime files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator

UTC = timezone.utc


def parse_utc_datetime(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp into a timezone-aware datetime.

    The public configuration format uses a trailing ``Z``.  Offsets are also
    accepted, but naive datetimes are rejected because cycle arithmetic must
    never depend on the machine timezone.
    """
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError(f"Datetime must include a timezone: {value}")
    return parsed.astimezone(UTC)


def format_cycle_id(value: datetime) -> str:
    """Return the compact cycle identifier used in runtime paths."""
    return value.astimezone(UTC).strftime("%Y%m%d%H")


def format_mpas_timestamp(value: datetime) -> str:
    """Return the MPAS filename timestamp convention used by the baseline."""
    return value.astimezone(UTC).strftime("%Y-%m-%d_%H.%M.%S")


@dataclass(frozen=True)
class CycleDefinition:
    """Minimal temporal definition for a sequence of analysis cycles.

    ``end`` is exclusive.  A one-day period starting at 00Z and ending at the
    next 00Z with a six-hour interval therefore produces 00Z, 06Z, 12Z and
    18Z exactly.

    ``background_offset_hours`` expresses the time of the state used by the
    variational application relative to the analysis time.  The validated
    3DVar-FGAT baseline uses ``-3`` hours: its analysis is at 00Z and its
    background is at 21Z.
    """

    start: datetime
    end: datetime
    interval: timedelta
    background_offset: timedelta
    window_length: timedelta

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Cycle bounds must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("cycle.end must be later than cycle.start")
        if self.interval <= timedelta(0):
            raise ValueError("cycle.interval must be positive")
        if self.background_offset > timedelta(0):
            raise ValueError("background_offset cannot be later than analysis time")
        if self.window_length <= timedelta(0):
            raise ValueError("window_length must be positive")

    @classmethod
    def from_mapping(cls, cycle: dict[str, object], *, background_offset_hours: int, window_length_hours: int) -> "CycleDefinition":
        """Build a definition from the minimal experiment ``cycle`` mapping."""
        try:
            start = parse_utc_datetime(str(cycle["start"]))
            end = parse_utc_datetime(str(cycle["end"]))
            interval_hours = int(cycle["interval_hours"])
        except KeyError as exc:
            raise KeyError(f"Missing required cycle key: {exc.args[0]}") from exc
        return cls(
            start=start,
            end=end,
            interval=timedelta(hours=interval_hours),
            background_offset=timedelta(hours=background_offset_hours),
            window_length=timedelta(hours=window_length_hours),
        )


@dataclass(frozen=True)
class CycleInstance:
    """Resolved time-dependent values for one analysis cycle."""

    analysis_time: datetime
    background_time: datetime
    window_begin: datetime
    window_end: datetime

    @property
    def cycle_id(self) -> str:
        """Compact analysis-time identifier, for example ``2018041500``."""
        return format_cycle_id(self.analysis_time)

    @property
    def mpas_background_file_date(self) -> str:
        """MPAS timestamp for the background filename."""
        return format_mpas_timestamp(self.background_time)


def iter_cycle_instances(definition: CycleDefinition) -> Iterator[CycleInstance]:
    """Yield resolved cycles in chronological order.

    The FGAT window starts at the background time for the current baseline
    convention.  This explicit relationship can later be generalized by a
    method component without changing callers of the timeline API.
    """
    analysis_time = definition.start
    while analysis_time < definition.end:
        background_time = analysis_time + definition.background_offset
        yield CycleInstance(
            analysis_time=analysis_time,
            background_time=background_time,
            window_begin=background_time,
            window_end=background_time + definition.window_length,
        )
        analysis_time += definition.interval


def resolve_cycle_instances(definition: CycleDefinition) -> list[CycleInstance]:
    """Return all instances as a list for planning and validation commands."""
    return list(iter_cycle_instances(definition))
