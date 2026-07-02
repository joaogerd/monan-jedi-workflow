"""Compile resolved V2 configuration into MPAS forecast stages."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from ....platforms.base import ExecutionBackend, ExecutionRequest
from .forecast import MpasForecastStage
from .output_validation import MpasOutputContract
from .products import MPAS_TIME_FORMAT, MpasForecastProductLayout


class MpasForecastConfigurationError(ValueError):
    """Raised when `model.mpas.forecast` configuration is invalid."""


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MpasForecastConfigurationError(f"{label} must be a mapping.")
    return value


def compile_mpas_forecast(
    config: Mapping[str, object],
    *,
    workspace: Path,
    init_time: str,
    lead_hours: int,
    backend: ExecutionBackend,
) -> MpasForecastStage:
    """Compile one configured MPAS forecast into an executable stage.

    Parameters
    ----------
    config : Mapping[str, object]
        Resolved case configuration.
    workspace : Path
        Explicit workflow workspace.
    init_time : str
        Forecast initialization time.
    lead_hours : int
        Positive forecast lead time.
    backend : ExecutionBackend
        Local or platform-specific execution backend.
    """
    model = _mapping(config.get("model"), "model")
    mpas = _mapping(model.get("mpas"), "model.mpas")
    forecast = _mapping(mpas.get("forecast"), "model.mpas.forecast")
    product = MpasForecastProductLayout.from_mapping(_mapping(mpas.get("forecast_products"), "model.mpas.forecast_products")).forecast(init_time, lead_hours)
    run_template = forecast.get("run_dir")
    argv = forecast.get("argv")
    if not isinstance(run_template, str) or not run_template or not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise MpasForecastConfigurationError("model.mpas.forecast requires non-empty run_dir and argv.")
    init = datetime.strptime(product.init_time, MPAS_TIME_FORMAT)
    valid = datetime.strptime(product.valid_time, MPAS_TIME_FORMAT)
    values = {
        "workspace": str(workspace), "init_time": product.init_time, "valid_time": product.valid_time,
        "init_yyyymmddhh": init.strftime("%Y%m%d%H"), "valid_yyyymmddhh": valid.strftime("%Y%m%d%H"),
        "lead_hours": lead_hours, "lead_hours_03d": f"{lead_hours:03d}",
    }
    try:
        run_dir = Path(run_template.format_map(values))
        run_dir = run_dir if run_dir.is_absolute() else workspace / run_dir
        command = tuple(item.format_map(values) for item in argv)
    except KeyError as exc:
        raise MpasForecastConfigurationError(f"MPAS forecast uses unknown placeholder: {exc.args[0]}") from exc
    environment = forecast.get("environment", {})
    if not isinstance(environment, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in environment.items()):
        raise MpasForecastConfigurationError("model.mpas.forecast.environment must map strings to strings.")
    validation = _mapping(forecast.get("validation", {}), "model.mpas.forecast.validation")
    outputs = validation.get("required_outputs", [])
    markers = validation.get("required_log_markers", [])
    if not isinstance(outputs, list) or not isinstance(markers, list) or not all(isinstance(item, str) and item for item in outputs + markers):
        raise MpasForecastConfigurationError("MPAS validation outputs and markers must be non-empty strings.")
    log = validation.get("log")
    if log is not None and not isinstance(log, str):
        raise MpasForecastConfigurationError("model.mpas.forecast.validation.log must be a string.")
    request = ExecutionRequest(command, run_dir, dict(environment), run_dir / "stdout.log", run_dir / "stderr.log")
    contract = MpasOutputContract(tuple(Path(item.format_map(values)) for item in outputs), Path(log.format_map(values)) if log else None, tuple(markers))
    return MpasForecastStage(product, run_dir, contract, request=request, backend=backend)
