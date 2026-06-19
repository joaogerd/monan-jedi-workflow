"""Pure time-resolution utilities for cyclic MONAN-JEDI experiments.

This module intentionally has no filesystem, renderer, scheduler or PBS
side-effects. It converts a declarative cycle definition into deterministic
analysis instances and FGAT trajectories that later workflow layers can render.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator

UTC = timezone.utc


def parse_utc_datetime(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp into a timezone-aware datetime."""
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
    """Temporal definition for a sequence of analysis cycles.

    ``end`` is exclusive. A one-day period from 00Z to the next 00Z with a
    six-hour interval therefore produces 00Z, 06Z, 12Z and 18Z.

    ``trajectory_offsets`` are the valid times used by FGAT relative to the
    analysis time. For the familiar GSI-style window ``[-3, 0, +3]`` and a
    six-hour cycle, the forecast starts at the previous analysis (T-6), runs
    nine hours, and contributes its 3 h, 6 h and 9 h outputs to analysis T.

    The forecast origin is deliberately explicit. It defaults to one cycle
    interval before the analysis, but another workflow profile may choose a
    different origin without changing the renderer or scheduler.
    """

    start: datetime
    end: datetime
    interval: timedelta
    trajectory_offsets: tuple[timedelta, ...]
    forecast_start_offset: timedelta | None = None

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Cycle bounds must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("cycle.end must be later than cycle.start")
        if self.interval <= timedelta(0):
            raise ValueError("cycle.interval must be positive")
        if not self.trajectory_offsets:
            raise ValueError("trajectory_offsets cannot be empty")
        if tuple(sorted(self.trajectory_offsets)) != self.trajectory_offsets:
            raise ValueError("trajectory_offsets must be strictly ordered")
        if len(set(self.trajectory_offsets)) != len(self.trajectory_offsets):
            raise ValueError("trajectory_offsets cannot contain duplicates")
        origin = self.effective_forecast_start_offset
        if origin >= min(self.trajectory_offsets):
            raise ValueError(
                "forecast_start_offset must be earlier than the first trajectory output"
            )

    @property
    def effective_forecast_start_offset(self) -> timedelta:
        """Return the forecast origin relative to analysis time."""
        return self.forecast_start_offset or -self.interval

    @classmethod
    def from_mapping(
        cls,
        cycle: dict[str, object],
        *,
        trajectory_offsets_hours: list[int],
        forecast_start_offset_hours: int | None = None,
    ) -> "CycleDefinition":
        """Build a definition from minimal cycle and method configuration."""
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
            trajectory_offsets=tuple(
                timedelta(hours=offset) for offset in trajectory_offsets_hours
            ),
            forecast_start_offset=(
                timedelta(hours=forecast_start_offset_hours)
                if forecast_start_offset_hours is not None
                else None
            ),
        )


@dataclass(frozen=True)
class TrajectoryState:
    """One model state sampled from the forecast trajectory used by FGAT."""

    valid_time: datetime
    offset_from_analysis: timedelta
    forecast_lead: timedelta

    @property
    def mpas_file_date(self) -> str:
        """MPAS timestamp expected in the trajectory output filename."""
        return format_mpas_timestamp(self.valid_time)


@dataclass(frozen=True)
class CycleInstance:
    """Resolved time-dependent values for one analysis cycle."""

    analysis_time: datetime
    forecast_start_time: datetime
    forecast_end_time: datetime
    trajectory: tuple[TrajectoryState, ...]

    @property
    def cycle_id(self) -> str:
        """Compact analysis-time identifier, for example ``2018041500``."""
        return format_cycle_id(self.analysis_time)

    @property
    def window_begin(self) -> datetime:
        """First valid time represented in the FGAT window."""
        return self.trajectory[0].valid_time

    @property
    def window_end(self) -> datetime:
        """Last valid time represented in the FGAT window."""
        return self.trajectory[-1].valid_time

    @property
    def forecast_length(self) -> timedelta:
        """Duration required to create every state in this trajectory."""
        return self.forecast_end_time - self.forecast_start_time

    @property
    def background_time(self) -> datetime:
        """Compatibility alias for the earliest trajectory state.

        New callers should use ``trajectory``. The alias keeps the first
        transition incremental while the existing baseline is decomposed.
        """
        return self.window_begin

    @property
    def mpas_background_file_date(self) -> str:
        """Compatibility timestamp for the earliest trajectory state."""
        return format_mpas_timestamp(self.background_time)


def iter_cycle_instances(definition: CycleDefinition) -> Iterator[CycleInstance]:
    """Yield resolved cycles and their required forecast trajectories."""
    analysis_time = definition.start
    forecast_origin_offset = definition.effective_forecast_start_offset

    while analysis_time < definition.end:
        forecast_start_time = analysis_time + forecast_origin_offset
        trajectory = tuple(
            TrajectoryState(
                valid_time=analysis_time + offset,
                offset_from_analysis=offset,
                forecast_lead=(analysis_time + offset) - forecast_start_time,
            )
            for offset in definition.trajectory_offsets
        )
        yield CycleInstance(
            analysis_time=analysis_time,
            forecast_start_time=forecast_start_time,
            forecast_end_time=trajectory[-1].valid_time,
            trajectory=trajectory,
        )
        analysis_time += definition.interval


def resolve_cycle_instances(definition: CycleDefinition) -> list[CycleInstance]:
    """Return all instances as a list for planning and validation commands."""
    return list(iter_cycle_instances(definition))
