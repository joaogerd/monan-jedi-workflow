"""Scientific time geometry for NMC forecast pairs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ...model.mpas.products import (
    MPAS_TIME_FORMAT,
    MpasForecastProduct,
    MpasProductLayoutError,
    normalize_mpas_time,
)


class NmcPairError(ValueError):
    """Raised when an NMC pair does not satisfy its scientific time contract."""


def normalize_time(value: str) -> str:
    """Normalize an NMC timestamp through the MPAS product time contract.

    Parameters
    ----------
    value : str
        MPAS or timezone-aware ISO-8601 timestamp.

    Returns
    -------
    str
        Canonical UTC timestamp in ``YYYY-MM-DD_HH:MM:SS`` form.

    Raises
    ------
    NmcPairError
        Raised when the shared MPAS time parser rejects the value.
    """
    try:
        return normalize_mpas_time(value)
    except MpasProductLayoutError as exc:
        raise NmcPairError(str(exc)) from exc


def _as_datetime(value: str) -> datetime:
    """Parse one canonical NMC timestamp as a UTC datetime."""
    return datetime.strptime(normalize_time(value), MPAS_TIME_FORMAT).replace(tzinfo=timezone.utc)


# Compatibility alias retained for callers that still import NmcForecast. Product
# identity belongs to the MPAS component; NMC adds only pair geometry semantics.
NmcForecast = MpasForecastProduct


@dataclass(frozen=True)
class NmcPair:
    """Describe one older/newer MPAS forecast pair with a common valid time.

    Parameters
    ----------
    valid_time : str
        Common valid time of both forecasts.
    older : MpasForecastProduct
        Earlier initialization with the longer lead time.
    newer : MpasForecastProduct
        Later initialization with the shorter lead time.
    """

    valid_time: str
    older: MpasForecastProduct
    newer: MpasForecastProduct

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


ForecastResolver = Callable[[str, int], MpasForecastProduct]


def _require_forecast_identity(
    forecast: MpasForecastProduct,
    *,
    requested_init_time: str,
    requested_lead_hours: int,
    label: str,
) -> None:
    """Reject a resolver product that differs from the requested identity."""
    if forecast.init_time != requested_init_time or forecast.lead_hours != requested_lead_hours:
        raise NmcPairError(
            f"Resolver returned inconsistent {label} forecast: expected "
            f"init={requested_init_time}, lead={requested_lead_hours}; received "
            f"init={forecast.init_time}, lead={forecast.lead_hours}."
        )


def plan_pairs(
    valid_times: Iterable[str],
    *,
    older_lead_hours: int,
    newer_lead_hours: int,
    resolve_forecast: ForecastResolver,
) -> tuple[NmcPair, ...]:
    """Plan NMC pairs for requested common valid times.

    Parameters
    ----------
    valid_times : Iterable[str]
        Requested common valid times.
    older_lead_hours : int
        Longer lead time assigned to the earlier initialization.
    newer_lead_hours : int
        Shorter lead time assigned to the later initialization.
    resolve_forecast : ForecastResolver
        Callback resolving one MPAS product identity to its artifact paths.

    Returns
    -------
    tuple[NmcPair, ...]
        Validated forecast-pair plan sorted by valid time.
    """
    if older_lead_hours <= newer_lead_hours:
        raise NmcPairError("older_lead_hours must be greater than newer_lead_hours.")
    normalized = sorted(normalize_time(item) for item in valid_times)
    if len(set(normalized)) != len(normalized):
        raise NmcPairError("NMC valid times must be unique.")

    pairs: list[NmcPair] = []
    for valid_time in normalized:
        valid = _as_datetime(valid_time)
        older_init = (valid - timedelta(hours=older_lead_hours)).strftime(MPAS_TIME_FORMAT)
        newer_init = (valid - timedelta(hours=newer_lead_hours)).strftime(MPAS_TIME_FORMAT)
        older = resolve_forecast(older_init, older_lead_hours)
        newer = resolve_forecast(newer_init, newer_lead_hours)
        _require_forecast_identity(older, requested_init_time=older_init, requested_lead_hours=older_lead_hours, label="older")
        _require_forecast_identity(newer, requested_init_time=newer_init, requested_lead_hours=newer_lead_hours, label="newer")
        pairs.append(NmcPair(valid_time, older, newer))
    return tuple(pairs)
