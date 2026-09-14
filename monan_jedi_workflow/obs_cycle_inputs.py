"""Resolve dated observation inputs against the requested analysis cycle."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_DATE_HOUR = re.compile(r"(?<!\d)(?:19|20)\d{8}(?!\d)")
_DATE = re.compile(r"(?<!\d)(?:19|20)\d{6}(?!\d)")
_T_HOUR = re.compile(r"t\d{2}z", re.IGNORECASE)


class ObservationInputError(RuntimeError):
    """An observation source is missing or belongs to a different cycle."""


@dataclass(frozen=True)
class InputResolution:
    converter: str
    cycle: str
    configured: str
    resolved: str

    def as_dict(self) -> dict[str, str]:
        return {
            "converter": self.converter,
            "cycle": self.cycle,
            "configured": self.configured,
            "resolved": self.resolved,
            "method": "cycle-pattern",
        }


def _looks_like_observation_data(path: Path) -> bool:
    name = path.name.lower()
    return "prepbufr" in name or "gpsro" in name or ".bufr" in name


def resolve_cycle_input(path: Path, cycle, converter: str) -> tuple[Path, InputResolution | None]:
    """Resolve a dated PREPBUFR/GPSRO path for ``cycle`` without wrong-cycle fallback."""
    if not _looks_like_observation_data(path):
        return path, None

    text = str(path)
    date_hours = set(_DATE_HOUR.findall(text))
    dates = set(_DATE.findall(text))
    t_hours = {item.lower() for item in _T_HOUR.findall(text)}
    if not date_hours and not dates and not t_hours:
        return path, None

    expected_10 = cycle.value.strftime("%Y%m%d%H")
    expected_8 = cycle.value.strftime("%Y%m%d")
    expected_t = cycle.value.strftime("t%Hz").lower()
    matches = (
        (not date_hours or expected_10 in date_hours)
        and (not dates or expected_8 in dates)
        and (not t_hours or expected_t in t_hours)
    )
    if matches:
        if not path.is_file():
            raise ObservationInputError(
                "Observation input not found for requested cycle\n"
                f"  Cycle: {cycle.cycle_time}\n"
                f"  Converter: {converter}\n"
                f"  Expected file: {path}"
            )
        return path, None

    candidate_text = _DATE_HOUR.sub(expected_10, text)
    candidate_text = _DATE.sub(expected_8, candidate_text)
    candidate_text = _T_HOUR.sub(cycle.value.strftime("t%Hz"), candidate_text)
    candidate = Path(candidate_text)
    if not candidate.is_file():
        raise ObservationInputError(
            "Observation input belongs to a different cycle and the matching local file was not found\n"
            f"  Requested cycle: {cycle.cycle_time}\n"
            f"  Converter: {converter}\n"
            f"  Configured input: {path}\n"
            f"  Expected candidate: {candidate}\n"
            "  The campaign was stopped before using wrong-cycle observations."
        )

    return candidate, InputResolution(
        converter=converter,
        cycle=cycle.cycle_time,
        configured=str(path),
        resolved=str(candidate),
    )
