"""Compile resolved V2 configuration into MPAS forecast stages."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from ....platforms.base import ExecutionBackend
from .forecast import MpasForecastStage
from .netcdf_contracts import MpasNetcdfContractError, mpas_artifact_check
from .output_validation import MpasOutputContract
from .products import MPAS_TIME_FORMAT, MpasForecastProductLayout, MpasProductLayoutError
from .runtime_config import CompiledMpasRuntime, MpasRuntimeConfigurationError, compile_runtime, require_mapping
from .staging import LinkSpec


class MpasForecastConfigurationError(MpasRuntimeConfigurationError):
    """Raised when `model.mpas.forecast` configuration is invalid."""


def _runtime_files(section: Mapping[str, object], runtime: CompiledMpasRuntime) -> tuple[LinkSpec, ...]:
    """Compile explicit top-level MPAS physics/runtime files for one forecast.

    The MPAS atmosphere installation carries required tables beside its namelist
    and streams templates. They are a scientific runtime input, not an implicit
    site-side effect. Templates remain rendered separately and are excluded from
    the staged support-file set.
    """
    raw = section.get("runtime_files")
    if raw is None:
        return ()
    values = require_mapping(raw, "model.mpas.forecast.runtime_files")
    unknown = set(values).difference({"source_dir", "exclude"})
    if unknown:
        raise MpasForecastConfigurationError(
            "model.mpas.forecast.runtime_files contains unsupported key(s): "
            + ", ".join(sorted(str(item) for item in unknown))
            + "."
        )
    source_value = values.get("source_dir")
    if not isinstance(source_value, str) or not source_value:
        raise MpasForecastConfigurationError("model.mpas.forecast.runtime_files.source_dir must be a non-empty string.")
    source_dir = Path(source_value)
    if not source_dir.is_absolute():
        raise MpasForecastConfigurationError("model.mpas.forecast.runtime_files.source_dir must be absolute.")
    if not source_dir.is_dir():
        raise MpasForecastConfigurationError(f"MPAS forecast runtime_files.source_dir does not exist: {source_dir}")

    raw_exclude = values.get("exclude", ["namelist.atmosphere", "streams.atmosphere"])
    if not isinstance(raw_exclude, list) or not all(isinstance(item, str) and item for item in raw_exclude):
        raise MpasForecastConfigurationError(
            "model.mpas.forecast.runtime_files.exclude must be a list of non-empty filenames."
        )
    excluded = set(raw_exclude)
    required_exclusions = {"namelist.atmosphere", "streams.atmosphere"}
    if not required_exclusions.issubset(excluded):
        missing = ", ".join(sorted(required_exclusions.difference(excluded)))
        raise MpasForecastConfigurationError(
            f"model.mpas.forecast.runtime_files.exclude must include rendered templates: {missing}."
        )

    occupied = {item.target.name for item in runtime.links} | {item.target.name for item in runtime.templates}
    links: list[LinkSpec] = []
    for source in sorted(source_dir.iterdir(), key=lambda item: item.name):
        if not source.is_file() or source.name in excluded:
            continue
        if source.name in occupied:
            raise MpasForecastConfigurationError(
                f"MPAS forecast runtime file target collides with declared link/template: {source.name}"
            )
        occupied.add(source.name)
        links.append(LinkSpec(source, runtime.run_dir / source.name))
    if not links:
        raise MpasForecastConfigurationError(
            f"MPAS forecast runtime_files.source_dir contains no staged regular files: {source_dir}"
        )
    return tuple(links)


def _baseline_values(section: Mapping[str, object]) -> dict[str, object]:
    """Compile declared producer-baseline overrides for forecast rendering."""
    raw_overrides = section.get("namelist_overrides", {})
    if not isinstance(raw_overrides, Mapping):
        raise MpasForecastConfigurationError("model.mpas.forecast.namelist_overrides must be a mapping.")
    overrides: dict[str, str] = {}
    for name, value in raw_overrides.items():
        if not isinstance(name, str) or not name or not isinstance(value, str) or not value:
            raise MpasForecastConfigurationError(
                "model.mpas.forecast.namelist_overrides must map non-empty strings to non-empty strings."
            )
        overrides[name] = value
    protected = {"config_start_time", "config_stop_time", "config_run_duration", "config_do_restart", "config_block_decomp_file_prefix"}
    collision = protected.intersection(overrides)
    if collision:
        raise MpasForecastConfigurationError(
            "model.mpas.forecast.namelist_overrides cannot replace generated values: " + ", ".join(sorted(collision))
        )

    output_interval = section.get("output_interval")
    if output_interval is not None and (not isinstance(output_interval, str) or not output_interval):
        raise MpasForecastConfigurationError("model.mpas.forecast.output_interval must be a non-empty string when set.")
    values: dict[str, object] = {"forecast_namelist_overrides": overrides}
    if output_interval is not None:
        values["forecast_output_interval"] = output_interval
    return values


def compile_mpas_forecast(
    config: Mapping[str, object],
    *,
    workspace: Path,
    init_time: str,
    lead_hours: int,
    backend: ExecutionBackend,
    extra_values: Mapping[str, object] | None = None,
) -> MpasForecastStage:
    """Compile one configured MPAS forecast into an executable stage."""
    try:
        model = require_mapping(config.get("model"), "model")
        mpas = require_mapping(model.get("mpas"), "model.mpas")
        section = require_mapping(mpas.get("forecast"), "model.mpas.forecast")
        layout = MpasForecastProductLayout.from_mapping(
            require_mapping(mpas.get("forecast_products"), "model.mpas.forecast_products")
        )
        product = layout.forecast(init_time, lead_hours)
        init = datetime.strptime(product.init_time, MPAS_TIME_FORMAT)
        valid = datetime.strptime(product.valid_time, MPAS_TIME_FORMAT)
        values: dict[str, object] = {
            "workspace": str(workspace),
            "init_time": product.init_time,
            "valid_time": product.valid_time,
            "init_yyyymmddhh": init.strftime("%Y%m%d%H"),
            "valid_yyyymmddhh": valid.strftime("%Y%m%d%H"),
            "mpas_valid_file_time": valid.strftime("%Y-%m-%d_%H.%M.%S"),
            "lead_hours": lead_hours,
            "lead_hours_03d": f"{lead_hours:03d}",
            "restart": str(product.restart),
            "state": str(product.state),
        }
        upstream = dict(extra_values or {})
        collision = set(values).intersection(upstream)
        if collision:
            raise MpasForecastConfigurationError(
                f"MPAS forecast extra values cannot override product tokens: {', '.join(sorted(collision))}."
            )
        values.update(upstream)
        runtime = compile_runtime(
            section,
            label="model.mpas.forecast",
            workspace=workspace,
            values=values,
            backend=backend,
        )
        support_links = _runtime_files(section, runtime)
        baseline_values = _baseline_values(section)
        initial_state = upstream.get("initial_state")
        links = tuple(
            LinkSpec(item.source, item.target, upstream_artifact=isinstance(initial_state, str) and item.source == Path(initial_state))
            for item in (*runtime.links, *support_links)
        )
        checks = tuple(
            check
            for check in (
                mpas_artifact_check(
                    config,
                    name="forecast_restart",
                    path=product.restart,
                    default_consumer="bmatrix.nmc_pairs",
                    expected_time=product.valid_time,
                ),
                mpas_artifact_check(
                    config,
                    name="forecast_state",
                    path=product.state,
                    default_consumer="bmatrix.nmc_pairs",
                    expected_time=product.valid_time,
                ),
            )
            if check is not None
        )
    except (MpasRuntimeConfigurationError, MpasProductLayoutError, MpasNetcdfContractError) as exc:
        raise MpasForecastConfigurationError(str(exc)) from exc
    contract = MpasOutputContract(
        required_files=runtime.contract.required_files,
        log_path=runtime.contract.log_path,
        required_log_markers=runtime.contract.required_log_markers,
        netcdf_checks=(*runtime.contract.netcdf_checks, *checks),
    )
    return MpasForecastStage(
        product,
        runtime.run_dir,
        contract,
        request=runtime.request,
        backend=backend,
        links=links,
        templates=runtime.templates,
        extra_values={**upstream, **baseline_values},
    )
