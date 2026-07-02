"""Scientific time geometry for NMC forecast pairs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


_TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


class NmcPairError(ValueError):
    """Raised when an NMC pair does not satisfy its scientific time contract."""


def normalize_time(value: str) -> str:
    """Normalize an ISO-8601 or MPAS timestamp to the canonical NMC form.

    Parameters
    ----------
    value : str
        Timestamp using either ``YYYY-MM-DD_HH:MM:SS`` or timezone-aware
        ISO-8601 syntax.

    Returns
    -------
    str
        Canonical UTC timestamp in ``YYYY-MM-DD_HH:MM:SS`` form.

    Raises
    ------
    NmcPairError
        Raised when the timestamp cannot be parsed or lacks timezone information
        in ISO-8601 form.
    """
    try:
        return datetime.strptime(value, _TIME_FORMAT).replace(tzinfo=timezone.utc).strftime(_TIME_FORMAT)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NmcPairError(f"Invalid NMC timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise NmcPairError(f"ISO-8601 NMC timestamp must include a timezone: {value}")
    return parsed.astimezone(timezone.utc).strftime(_TIME_FORMAT)


def _as_datetime(value: str) -> datetime:
    return datetime.strptime(normalize_time(value), _TIME_FORMAT).replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class NmcForecast:
    """Describe forecast products from one MPAS initialization and lead time.

    Parameters
    ----------
    init_time : str
        Initialization timestamp.
    lead_hours : int
        Forecast lead time in hours.
    restart : Path
        Required restart product used to validate forecast completion.
    state : Path
        MPAS state product consumed by BFLOW.
    """

    init_time: str
    lead_hours: int
    restart: Path
    state: Path

    def __post_init__(self) -> None:
        """Normalize the initialization time and validate the positive lead."""
        if self.lead_hours <= 0:
            raise NmcPairError("Forecast lead_hours must be positive.")
        object.__setattr__(self, "init_time", normalize_time(self.init_time))

    @property
    def valid_time(self) -> str:
        """Return the forecast valid time derived from initialization and lead."""
        return (_as_datetime(self.init_time) + timedelta(hours=self.lead_hours)).strftime(_TIME_FORMAT)


@dataclass(frozen=True)
class NmcPair:
    """Describe one older/newer NMC forecast pair with a common valid time.

    Parameters
    ----------
    valid_time : str
        Common valid time of both forecasts.
    older : NmcForecast
        Forecast initialized earlier with the longer lead time.
    newer : NmcForecast
        Forecast initialized later with the shorter lead time.

    Raises
    ------
    NmcPairError
        Raised when forecast valid times differ or the older forecast does not
        have a longer lead time.
    """

    valid_time: str
    older: NmcForecast
    newer: NmcForecast

    def __post_init__(self) -> None:
        """Validate the shared valid-time and ordering invariants."""
        normalized = normalize_time(self.valid_time)
        object.__setattr__(self, "valid_time", normalized)
        if self.older.valid_time != normalized or self.newer.valid_time != normalized:
            raise NmcPairError(
                "NMC pair forecasts must share the declared valid time: "
                f"older={self.older.valid_time}, newer={self.newer.valid_time}, declared={normalized}."
            )
        if self.older.lead_hours <= self.newer.lead_hours:
            raise NmcPairError("The older NMC forecast must have a longer lead time than the newer forecast.")
        if _as_datetime(self.older.init_time) >= _as_datetime(self.newer.init_time):
            raise NmcPairError("The older NMC forecast must have an earlier initialization time.")


ForecastResolver = Callable[[str, int], NmcForecast]


def plan_pairs(
    valid_times: Iterable[str],
    *,
    older_lead_hours: int,
    newer_lead_hours: int,
    resolve_forecast: ForecastResolver,
) -> tuple[NmcPair, ...]:
    """Plan NMC pairs for requested valid times.

    Parameters
    ----------
    valid_times : Iterable[str]
        Requested common valid times.
    older_lead_hours : int
        Longer lead time assigned to the earlier initialization.
    newer_lead_hours : int
        Shorter lead time assigned to the later initialization.
    resolve_forecast : ForecastResolver
        Callback resolving one initialization/lead combination to expected MPAS
        restart and state products.

    Returns
    -------
    tuple[NmcPair, ...]
        Validated forecast-pair plan sorted by valid time.

    Raises
    ------
    NmcPairError
        Raised when leads are invalid, valid times are duplicated, or a resolver
        returns products inconsistent with the requested time geometry.
    """
    if older_lead_hours <= newer_lead_hours:
        raise NmcPairError("older_lead_hours must be greater than newer_lead_hours.")
    normalized = sorted(normalize_time(item) for item in valid_times)
    if len(set(normalized)) != len(normalized):
        raise NmcPairError("NMC valid times must be unique.")

    pairs: list[NmcPair] = []
    for valid_time in normalized:
        valid = _as_datetime(valid_time)
        older_init = (valid - timedelta(hours=older_lead_hours)).strftime(_TIME_FORMAT)
        newer_init = (valid - timedelta(hours=newer_lead_hours)).strftime(_TIME_FORMAT)
        older = resolve_forecast(older_init, older_lead_hours)
        newer = resolve_forecast(newer_init, newer_lead_hours)
        pairs.append(NmcPair(valid_time, older, newer))
    return tuple(pairs)
