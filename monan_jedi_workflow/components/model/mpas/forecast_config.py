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
from .runtime_config import MpasRuntimeConfigurationError, compile_runtime, require_mapping


class MpasForecastConfigurationError(MpasRuntimeConfigurationError):
    """Raised when `model.mpas.forecast` configuration is invalid."""


def compile_mpas_forecast(
    config: Mapping[str, object],
    *,
    workspace: Path,
    init_time: str,
    lead_hours: int,
    backend: ExecutionBackend,
    extra_values: Mapping[str, object] | None = None,
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
    extra_values : Mapping[str, object] | None, default=None
        Explicit upstream artifact values available to path, command, and
        template rendering. Core product tokens cannot be overridden.

    Returns
    -------
    MpasForecastStage
        Stage with explicit runtime, staging, output, and NetCDF contracts.
    """
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
        links=runtime.links,
        templates=runtime.templates,
        extra_values=upstream,
    )
