"""Explicit MPAS forecast-product location contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Formatter

from ...bmatrix.nmc_pairs.model import NmcForecast, normalize_time


class MpasProductLayoutError(ValueError):
    """Raised when an MPAS forecast-product layout cannot be rendered."""


_TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


def _time_context(init_time: str, lead_hours: int) -> dict[str, str | int]:
    """Build documented template values for one MPAS forecast product.

    Parameters
    ----------
    init_time : str
        Forecast initialization time.
    lead_hours : int
        Positive forecast lead time in hours.

    Returns
    -------
    dict[str, str | int]
        Initialization, valid-time, and lead-time template values.
    """
    normalized = normalize_time(init_time)
    if lead_hours <= 0:
        raise MpasProductLayoutError("MPAS forecast lead_hours must be positive.")
    init = datetime.strptime(normalized, _TIME_FORMAT).replace(tzinfo=timezone.utc)
    valid = init + timedelta(hours=lead_hours)
    return {
        "init_time": normalized,
        "init_yyyymmddhh": init.strftime("%Y%m%d%H"),
        "valid_time": valid.strftime(_TIME_FORMAT),
        "valid_yyyymmddhh": valid.strftime("%Y%m%d%H"),
        "mpas_valid_file_time": valid.strftime("%Y-%m-%d_%H.%M.%S"),
        "lead_hours": lead_hours,
        "lead_hours_03d": f"{lead_hours:03d}",
    }


def _fields(template: str) -> set[str]:
    """Return the named replacement fields referenced by a format template."""
    return {field_name for _, field_name, _, _ in Formatter().parse(template) if field_name}


def _required_string(mapping: Mapping[str, object], key: str, label: str) -> str:
    """Return one required non-empty configuration string."""
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise MpasProductLayoutError(f"{label}.{key} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class MpasForecastProductLayout:
    """Resolve restart and state products for one MPAS forecast.

    Parameters
    ----------
    root : Path
        Directory under which relative product templates are resolved.
    restart_template : str
        Relative or absolute Python-format path for the restart product.
    state_template : str
        Relative or absolute Python-format path for the MPAS state product.

    Notes
    -----
    Supported replacement fields are ``init_time``, ``init_yyyymmddhh``,
    ``valid_time``, ``valid_yyyymmddhh``, ``mpas_valid_file_time``,
    ``lead_hours``, and ``lead_hours_03d``.
    """

    root: Path
    restart_template: str
    state_template: str

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "MpasForecastProductLayout":
        """Build a product layout from `model.mpas.forecast_products` settings.

        Parameters
        ----------
        mapping : Mapping[str, object]
            Mapping with `root`, `restart_template`, and `state_template` keys.

        Returns
        -------
        MpasForecastProductLayout
            Validated product-layout declaration.
        """
        return cls(
            root=Path(_required_string(mapping, "root", "model.mpas.forecast_products")),
            restart_template=_required_string(mapping, "restart_template", "model.mpas.forecast_products"),
            state_template=_required_string(mapping, "state_template", "model.mpas.forecast_products"),
        )

    def __post_init__(self) -> None:
        """Validate templates before a campaign attempts to resolve products."""
        allowed = set(_time_context("2000-01-01_00:00:00", 1))
        for label, template in (("restart_template", self.restart_template), ("state_template", self.state_template)):
            if not template:
                raise MpasProductLayoutError(f"MPAS {label} must be non-empty.")
            unknown = _fields(template).difference(allowed)
            if unknown:
                values = ", ".join(sorted(unknown))
                raise MpasProductLayoutError(f"MPAS {label} uses unsupported field(s): {values}.")

    def _render(self, template: str, context: Mapping[str, str | int]) -> Path:
        """Render one product template and resolve relative paths under `root`."""
        try:
            rendered = template.format_map(context)
        except (KeyError, ValueError) as exc:
            raise MpasProductLayoutError(f"Cannot render MPAS product template: {template}") from exc
        path = Path(rendered)
        return path if path.is_absolute() else self.root / path

    def forecast(self, init_time: str, lead_hours: int) -> NmcForecast:
        """Resolve expected MPAS products for one initialization and lead.

        Parameters
        ----------
        init_time : str
            Forecast initialization time.
        lead_hours : int
            Positive forecast lead time in hours.

        Returns
        -------
        NmcForecast
            Forecast identity and expected restart/state product paths.
        """
        context = _time_context(init_time, lead_hours)
        return NmcForecast(
            init_time=str(context["init_time"]),
            lead_hours=lead_hours,
            restart=self._render(self.restart_template, context),
            state=self._render(self.state_template, context),
        )
