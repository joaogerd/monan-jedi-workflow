"""Compile resolved V2 configuration into MPAS forecast stages."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from ....platforms.base import ExecutionBackend, ExecutionRequest
from .forecast import MpasForecastStage
from .output_validation import MpasOutputContract
from .products import MPAS_TIME_FORMAT, MpasForecastProductLayout
from .staging import LinkSpec, TemplateSpec


class MpasForecastConfigurationError(ValueError):
    """Raised when `model.mpas.forecast` configuration is invalid."""


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MpasForecastConfigurationError(f"{label} must be a mapping.")
    return value


def _staging(raw: object, label: str, values: Mapping[str, object], workspace: Path, run_dir: Path, kind: type[LinkSpec] | type[TemplateSpec]) -> tuple[LinkSpec, ...] | tuple[TemplateSpec, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise MpasForecastConfigurationError(f"{label} must be a list.")
    result = []
    for index, item in enumerate(raw):
        entry = _mapping(item, f"{label}[{index}]")
        source, target = entry.get("source"), entry.get("target")
        if not isinstance(source, str) or not source or not isinstance(target, str) or not target:
            raise MpasForecastConfigurationError(f"{label}[{index}] requires non-empty source and target.")
        try:
            source_path, target_path = Path(source.format_map(values)), Path(target.format_map(values))
        except KeyError as exc:
            raise MpasForecastConfigurationError(f"{label}[{index}] uses unknown placeholder: {exc.args[0]}") from exc
        result.append(kind(source_path if source_path.is_absolute() else workspace / source_path, target_path if target_path.is_absolute() else run_dir / target_path))
    return tuple(result)


def compile_mpas_forecast(config: Mapping[str, object], *, workspace: Path, init_time: str, lead_hours: int, backend: ExecutionBackend) -> MpasForecastStage:
    """Compile one configured MPAS forecast into an executable stage."""
    model = _mapping(config.get("model"), "model")
    mpas = _mapping(model.get("mpas"), "model.mpas")
    forecast = _mapping(mpas.get("forecast"), "model.mpas.forecast")
    product = MpasForecastProductLayout.from_mapping(_mapping(mpas.get("forecast_products"), "model.mpas.forecast_products")).forecast(init_time, lead_hours)
    run_template, argv = forecast.get("run_dir"), forecast.get("argv")
    if not isinstance(run_template, str) or not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise MpasForecastConfigurationError("model.mpas.forecast requires non-empty run_dir and argv.")
    init, valid = datetime.strptime(product.init_time, MPAS_TIME_FORMAT), datetime.strptime(product.valid_time, MPAS_TIME_FORMAT)
    values = {"workspace": str(workspace), "init_time": product.init_time, "valid_time": product.valid_time, "init_yyyymmddhh": init.strftime("%Y%m%d%H"), "valid_yyyymmddhh": valid.strftime("%Y%m%d%H"), "mpas_valid_file_time": valid.strftime("%Y-%m-%d_%H.%M.%S"), "lead_hours": lead_hours, "lead_hours_03d": f"{lead_hours:03d}", "restart": str(product.restart), "state": str(product.state)}
    try:
        candidate = Path(run_template.format_map(values))
        run_dir = candidate if candidate.is_absolute() else workspace / candidate
        command = tuple(item.format_map(values) for item in argv)
    except KeyError as exc:
        raise MpasForecastConfigurationError(f"MPAS forecast uses unknown placeholder: {exc.args[0]}") from exc
    environment = forecast.get("environment", {})
    if not isinstance(environment, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in environment.items()):
        raise MpasForecastConfigurationError("model.mpas.forecast.environment must map strings to strings.")
    validation = _mapping(forecast.get("validation", {}), "model.mpas.forecast.validation")
    outputs, markers, log = validation.get("required_outputs", []), validation.get("required_log_markers", []), validation.get("log")
    if not isinstance(outputs, list) or not isinstance(markers, list) or not all(isinstance(item, str) and item for item in outputs + markers) or (log is not None and not isinstance(log, str)):
        raise MpasForecastConfigurationError("MPAS validation values are invalid.")
    request = ExecutionRequest(command, run_dir, {key: value.format_map(values) for key, value in environment.items()}, run_dir / "stdout.log", run_dir / "stderr.log")
    contract = MpasOutputContract(tuple(Path(item.format_map(values)) for item in outputs), Path(log.format_map(values)) if log else None, tuple(markers))
    links = _staging(forecast.get("links"), "model.mpas.forecast.links", values, workspace, run_dir, LinkSpec)
    templates = _staging(forecast.get("templates"), "model.mpas.forecast.templates", values, workspace, run_dir, TemplateSpec)
    return MpasForecastStage(product, run_dir, contract, request=request, backend=backend, links=links, templates=templates)
