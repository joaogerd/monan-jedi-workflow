"""Configuration parsing for the NMC pair hand-off stage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .model import NmcPairError, normalize_time
from .validation import MINIMUM_BMATRIX_PAIRS


_TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


class NmcPairsConfigurationError(ValueError):
    """Raised when the NMC pair stage configuration is invalid."""


def _mapping(value: object, label: str) -> Mapping[str, object]:
    """Return a configuration mapping or raise an explicit error."""
    if not isinstance(value, Mapping):
        raise NmcPairsConfigurationError(f"{label} must be a mapping.")
    return value


def _string(mapping: Mapping[str, object], key: str, label: str, *, default: str | None = None) -> str:
    """Read one required or defaulted non-empty configuration string."""
    value = mapping.get(key, default)
    if not isinstance(value, str) or not value:
        raise NmcPairsConfigurationError(f"{label}.{key} must be a non-empty string.")
    return value


def _positive_int(mapping: Mapping[str, object], key: str, label: str, *, default: int | None = None) -> int:
    """Read one required or defaulted positive integer configuration value."""
    value = mapping.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise NmcPairsConfigurationError(f"{label}.{key} must be a positive integer.") from exc
    if parsed < 1:
        raise NmcPairsConfigurationError(f"{label}.{key} must be a positive integer.")
    return parsed


@dataclass(frozen=True)
class NmcPairsSettings:
    """User-facing settings for the NMC pair hand-off stage.

    Parameters
    ----------
    start_valid_time : str
        First inclusive valid time of the campaign.
    end_valid_time : str
        Last inclusive valid time of the campaign.
    interval_hours : int
        Spacing between valid times in hours.
    older_lead_hours : int
        Lead time of the earlier forecast, normally 48 hours.
    newer_lead_hours : int
        Lead time of the later forecast, normally 24 hours.
    minimum_pairs : int
        Minimum number of complete pairs required for B-matrix calibration.
    manifest_relative_path : Path
        BFLOW manifest path relative to the workflow workspace.
    report_relative_path : Path
        Validation report path relative to the workflow workspace.
    """

    start_valid_time: str
    end_valid_time: str
    interval_hours: int
    older_lead_hours: int
    newer_lead_hours: int
    minimum_pairs: int
    manifest_relative_path: Path
    report_relative_path: Path

    @classmethod
    def from_config(cls, config: Mapping[str, object]) -> "NmcPairsSettings":
        """Parse settings from the resolved `bmatrix.nmc_pairs` mapping.

        Parameters
        ----------
        config : Mapping[str, object]
            Fully resolved workflow configuration.

        Returns
        -------
        NmcPairsSettings
            Validated user-facing NMC stage settings.
        """
        bmatrix = _mapping(config.get("bmatrix"), "bmatrix")
        values = _mapping(bmatrix.get("nmc_pairs"), "bmatrix.nmc_pairs")
        label = "bmatrix.nmc_pairs"
        start = normalize_time(_string(values, "start_valid_time", label))
        end = normalize_time(_string(values, "end_valid_time", label))
        interval = _positive_int(values, "interval_hours", label, default=24)
        older = _positive_int(values, "older_lead_hours", label, default=48)
        newer = _positive_int(values, "newer_lead_hours", label, default=24)
        minimum = _positive_int(values, "minimum_pairs", label, default=MINIMUM_BMATRIX_PAIRS)
        if minimum < MINIMUM_BMATRIX_PAIRS:
            raise NmcPairsConfigurationError(
                f"{label}.minimum_pairs must be at least {MINIMUM_BMATRIX_PAIRS}."
            )
        if older <= newer:
            raise NmcPairsConfigurationError(f"{label}.older_lead_hours must be greater than newer_lead_hours.")

        manifest = Path(_string(values, "manifest_path", label, default="artifacts/bmatrix/nmc_pairs/bflow-manifest.tsv"))
        report = Path(_string(values, "report_path", label, default="artifacts/bmatrix/nmc_pairs/validation-report.json"))
        if manifest.is_absolute() or report.is_absolute():
            raise NmcPairsConfigurationError(
                f"{label}.manifest_path and {label}.report_path must be relative to the workflow workspace."
            )
        return cls(start, end, interval, older, newer, minimum, manifest, report)

    def valid_times(self) -> tuple[str, ...]:
        """Return every inclusive campaign valid time in canonical UTC form.

        Returns
        -------
        tuple[str, ...]
            Sorted inclusive campaign valid times.

        Raises
        ------
        NmcPairsConfigurationError
            Raised when the end time precedes the start time or is not aligned to
            `interval_hours`.
        """
        start = datetime.strptime(self.start_valid_time, _TIME_FORMAT).replace(tzinfo=timezone.utc)
        end = datetime.strptime(self.end_valid_time, _TIME_FORMAT).replace(tzinfo=timezone.utc)
        if end < start:
            raise NmcPairsConfigurationError("bmatrix.nmc_pairs.end_valid_time precedes start_valid_time.")
        values: list[str] = []
        current = start
        while current <= end:
            values.append(current.strftime(_TIME_FORMAT))
            current += timedelta(hours=self.interval_hours)
        if values[-1] != self.end_valid_time:
            raise NmcPairsConfigurationError(
                "bmatrix.nmc_pairs.end_valid_time is not aligned with interval_hours."
            )
        return tuple(values)


def mpas_product_settings(config: Mapping[str, object]) -> Mapping[str, object]:
    """Extract the `model.mpas.forecast_products` mapping from resolved config.

    Parameters
    ----------
    config : Mapping[str, object]
        Fully resolved workflow configuration.

    Returns
    -------
    Mapping[str, object]
        MPAS product-layout configuration used to resolve forecast artifacts.
    """
    model = _mapping(config.get("model"), "model")
    mpas = _mapping(model.get("mpas"), "model.mpas")
    return _mapping(mpas.get("forecast_products"), "model.mpas.forecast_products")
