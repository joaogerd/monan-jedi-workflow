"""MPAS forecast product contracts and path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Formatter
from typing import Mapping

MPAS_TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


class MpasProductLayoutError(ValueError):
    """Raised for invalid MPAS product settings or timestamps."""


def normalize_mpas_time(value: str) -> str:
    """Normalize MPAS or timezone-aware ISO-8601 time to UTC.

    Parameters
    ----------
    value : str
        MPAS or ISO-8601 timestamp.

    Returns
    -------
    str
        Canonical MPAS UTC timestamp.
    """
    try:
        return datetime.strptime(value, MPAS_TIME_FORMAT).replace(tzinfo=timezone.utc).strftime(MPAS_TIME_FORMAT)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MpasProductLayoutError(f"Invalid MPAS timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise MpasProductLayoutError(f"ISO-8601 MPAS timestamp must include a timezone: {value}")
    return parsed.astimezone(timezone.utc).strftime(MPAS_TIME_FORMAT)


@dataclass(frozen=True)
class MpasForecastProduct:
    """Restart and state artifacts produced by one MPAS forecast."""

    init_time: str
    lead_hours: int
    restart: Path
    state: Path

    def __post_init__(self) -> None:
        """Normalize time and reject non-positive forecast leads."""
        if self.lead_hours <= 0:
            raise MpasProductLayoutError("MPAS forecast lead_hours must be positive.")
        object.__setattr__(self, "init_time", normalize_mpas_time(self.init_time))

    @property
    def valid_time(self) -> str:
        """Return valid time derived from initialization and lead time."""
        init = datetime.strptime(self.init_time, MPAS_TIME_FORMAT).replace(tzinfo=timezone.utc)
        return (init + timedelta(hours=self.lead_hours)).strftime(MPAS_TIME_FORMAT)


def _context(init_time: str, lead_hours: int) -> dict[str, str | int]:
    normalized = normalize_mpas_time(init_time)
    if lead_hours <= 0:
        raise MpasProductLayoutError("MPAS forecast lead_hours must be positive.")
    init = datetime.strptime(normalized, MPAS_TIME_FORMAT).replace(tzinfo=timezone.utc)
    valid = init + timedelta(hours=lead_hours)
    return {
        "init_time": normalized,
        "init_yyyymmddhh": init.strftime("%Y%m%d%H"),
        "valid_time": valid.strftime(MPAS_TIME_FORMAT),
        "valid_yyyymmddhh": valid.strftime("%Y%m%d%H"),
        "mpas_valid_file_time": valid.strftime("%Y-%m-%d_%H.%M.%S"),
        "lead_hours": lead_hours,
        "lead_hours_03d": f"{lead_hours:03d}",
    }


@dataclass(frozen=True)
class MpasForecastProductLayout:
    """Resolve MPAS output paths from explicit documented templates."""

    root: Path
    restart_template: str
    state_template: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "MpasForecastProductLayout":
        """Build a layout from `model.mpas.forecast_products` settings."""
        try:
            root = values["root"]
            restart = values["restart_template"]
            state = values["state_template"]
        except KeyError as exc:
            raise MpasProductLayoutError(f"model.mpas.forecast_products missing {exc.args[0]}.") from exc
        if not all(isinstance(value, str) and value for value in (root, restart, state)):
            raise MpasProductLayoutError("MPAS forecast product settings must be non-empty strings.")
        return cls(Path(root), restart, state)

    def __post_init__(self) -> None:
        """Reject unsupported placeholders before running a forecast."""
        allowed = set(_context("2000-01-01_00:00:00", 1))
        for template in (self.restart_template, self.state_template):
            names = {name for _, name, _, _ in Formatter().parse(template) if name}
            unknown = names.difference(allowed)
            if unknown:
                raise MpasProductLayoutError(f"Unsupported MPAS path field(s): {', '.join(sorted(unknown))}.")

    def forecast(self, init_time: str, lead_hours: int) -> MpasForecastProduct:
        """Resolve the expected restart and state path for one forecast."""
        context = _context(init_time, lead_hours)
        def path(template: str) -> Path:
            rendered = Path(template.format_map(context))
            return rendered if rendered.is_absolute() else self.root / rendered
        return MpasForecastProduct(str(context["init_time"]), lead_hours, path(self.restart_template), path(self.state_template))
