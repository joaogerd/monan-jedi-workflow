"""Cycle-time parsing and template context shared by MPAS and Obs2IODA stages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class CycleTimeError(ValueError):
    """Raised when a stage receives an invalid cycle timestamp."""


@dataclass(frozen=True)
class CycleContext:
    """Normalized time values available to domain-stage configuration templates."""

    value: datetime

    @property
    def cycle_time(self) -> str:
        return self.value.isoformat(timespec="seconds").replace("+00:00", "Z")

    @property
    def cycle_id(self) -> str:
        return self.value.strftime("%Y%m%dT%H%M%SZ")

    @property
    def mpas_time(self) -> str:
        return self.value.strftime("%Y-%m-%d_%H:%M:%S")

    def valid_time(self, lead_hours: int) -> datetime:
        if lead_hours < 0:
            raise CycleTimeError("lead_hours must not be negative.")
        return self.value + timedelta(hours=lead_hours)

    def render_context(self, *, lead_hours: int = 0) -> dict[str, str]:
        valid = self.valid_time(lead_hours)
        return {
            "cycle_time": self.cycle_time,
            "cycle_id": self.cycle_id,
            "cycle_yyyymmddhh": self.value.strftime("%Y%m%d%H"),
            "cycle_year": self.value.strftime("%Y"),
            "cycle_month": self.value.strftime("%m"),
            "cycle_day": self.value.strftime("%d"),
            "cycle_hour": self.value.strftime("%H"),
            "mpas_time": self.mpas_time,
            "valid_time": valid.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "valid_id": valid.strftime("%Y%m%dT%H%M%SZ"),
            "mpas_valid_time": valid.strftime("%Y-%m-%d_%H:%M:%S"),
            "lead_hours": str(lead_hours),
        }


def parse_cycle_time(value: str) -> CycleContext:
    """Parse one timezone-aware ISO-8601 cycle time into a reusable context."""
    if not isinstance(value, str) or not value:
        raise CycleTimeError("cycle time must be a non-empty ISO-8601 timestamp.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise CycleTimeError(f"Invalid cycle time: {value!r}") from error
    if parsed.tzinfo is None:
        raise CycleTimeError("cycle time must include a UTC offset or trailing Z.")
    return CycleContext(parsed.astimezone(timezone.utc))
