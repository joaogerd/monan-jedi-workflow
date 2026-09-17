"""Resolve dated observation inputs against the requested analysis cycle."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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
    method: str = "cycle-pattern"

    def as_dict(self) -> dict[str, str]:
        return {
            "converter": self.converter,
            "cycle": self.cycle,
            "configured": self.configured,
            "resolved": self.resolved,
            "method": self.method,
        }


def _looks_like_observation_data(path: Path) -> bool:
    name = path.name.lower()
    return "prepbufr" in name or "gpsro" in name or ".bufr" in name


def cycle_candidate(path: Path, cycle) -> tuple[Path, bool]:
    """Return the same dated path rendered for ``cycle`` and whether it changed."""
    if not _looks_like_observation_data(path):
        return path, False

    text = str(path)
    date_hours = set(_DATE_HOUR.findall(text))
    dates = set(_DATE.findall(text))
    t_hours = {item.lower() for item in _T_HOUR.findall(text)}
    if not date_hours and not dates and not t_hours:
        return path, False

    expected_10 = cycle.value.strftime("%Y%m%d%H")
    expected_8 = cycle.value.strftime("%Y%m%d")
    expected_t = cycle.value.strftime("t%Hz").lower()
    matches = (
        (not date_hours or expected_10 in date_hours)
        and (not dates or expected_8 in dates)
        and (not t_hours or expected_t in t_hours)
    )
    if matches:
        return path, False

    candidate_text = _DATE_HOUR.sub(expected_10, text)
    candidate_text = _DATE.sub(expected_8, candidate_text)
    candidate_text = _T_HOUR.sub(cycle.value.strftime("t%Hz"), candidate_text)
    return Path(candidate_text), True


def _local_candidates(root: Path, candidate: Path, cycle, converter: str) -> list[Path]:
    """Build bounded, deterministic local candidates without walking whole filesystems."""
    date = cycle.value.strftime("%Y%m%d")
    year = cycle.value.strftime("%Y")
    month = cycle.value.strftime("%m")
    day = cycle.value.strftime("%d")
    hour = cycle.value.strftime("%H")
    name = candidate.name

    paths = [
        root / date / name,
        root / year / name,
        root / name,
    ]
    lower = converter.lower()
    if "prepbufr" in lower:
        paths.extend(
            [
                root / year / month / day / f"inpe.t{hour}z.prepbufr.nr",
                root / year / month / day / name,
            ]
        )
    elif "gpsro" in lower or "gnssro" in lower:
        paths.extend(
            [
                root / year / month / day / name,
                root / date / f"gdas.gpsro.t{hour}z.{date}.bufr",
                root / year / f"gdas.gpsro.t{hour}z.{date}.bufr",
            ]
        )

    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_local_cycle_input(
    candidate: Path,
    cycle,
    converter: str,
    search_roots: Iterable[Path] = (),
) -> Path | None:
    """Find one exact-cycle observation in configured local roots."""
    if candidate.is_file():
        return candidate
    for root in search_roots:
        root = Path(root).expanduser()
        if not root.is_dir():
            continue
        for path in _local_candidates(root, candidate, cycle, converter):
            if path.is_file():
                return path
    return None


def resolve_cycle_input(
    path: Path,
    cycle,
    converter: str,
    *,
    search_roots: Iterable[Path] = (),
) -> tuple[Path, InputResolution | None]:
    """Resolve a dated PREPBUFR/GPSRO path without ever using another cycle."""
    if not _looks_like_observation_data(path):
        return path, None

    candidate, changed = cycle_candidate(path, cycle)
    found = find_local_cycle_input(candidate, cycle, converter, search_roots)
    if found is not None:
        if not changed and found == path:
            return path, None
        method = "cycle-pattern" if found == candidate else "local-search"
        return found, InputResolution(
            converter=converter,
            cycle=cycle.cycle_time,
            configured=str(path),
            resolved=str(found),
            method=method,
        )

    if not changed:
        raise ObservationInputError(
            "Observation input not found for requested cycle\n"
            f"  Cycle: {cycle.cycle_time}\n"
            f"  Converter: {converter}\n"
            f"  Expected file: {candidate}"
        )

    roots = [str(Path(root).expanduser()) for root in search_roots]
    searched = f"\n  Local search roots: {', '.join(roots)}" if roots else ""
    raise ObservationInputError(
        "Observation input belongs to a different cycle and no matching local file was found\n"
        f"  Requested cycle: {cycle.cycle_time}\n"
        f"  Converter: {converter}\n"
        f"  Configured input: {path}\n"
        f"  Expected candidate: {candidate}"
        f"{searched}\n"
        "  The campaign was stopped before using wrong-cycle observations."
    )
