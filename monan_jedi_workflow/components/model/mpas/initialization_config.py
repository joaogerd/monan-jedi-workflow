"""Compile resolved V2 configuration into MPAS initialization stages."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ....platforms.base import ExecutionBackend
from .initialization import (
    MpasInitializationProductLayout,
    MpasInitializationStage,
    mpas_initialization_context,
)
from .netcdf_contracts import MpasNetcdfContractError, mpas_artifact_check
from .output_validation import MpasOutputContract
from .products import MpasProductLayoutError
from .runtime_config import MpasRuntimeConfigurationError, compile_runtime, require_mapping


class MpasInitializationConfigurationError(MpasRuntimeConfigurationError):
    """Raised when `model.mpas.initialization` configuration is invalid."""


def compile_mpas_initialization(
    config: Mapping[str, object],
    *,
    workspace: Path,
    cycle_time: str,
    backend: ExecutionBackend,
) -> MpasInitializationStage:
    """Compile one configured MPAS initialization into an executable stage.

    Parameters
    ----------
    config : Mapping[str, object]
        Resolved case configuration.
    workspace : Path
        Explicit workflow workspace.
    cycle_time : str
        Initialization or analysis time.
    backend : ExecutionBackend
        Local or platform-specific execution backend.

    Returns
    -------
    MpasInitializationStage
        Stage with explicit runtime, staging, output, and NetCDF contracts.
    """
    try:
        model = require_mapping(config.get("model"), "model")
        mpas = require_mapping(model.get("mpas"), "model.mpas")
        section = require_mapping(mpas.get("initialization"), "model.mpas.initialization")
        layout = MpasInitializationProductLayout.from_mapping(
            require_mapping(mpas.get("initialization_products"), "model.mpas.initialization_products")
        )
        product = layout.initialize(cycle_time)
        values = {
            "workspace": str(workspace),
            **mpas_initialization_context(product.cycle_time),
            "state": str(product.state),
        }
        runtime = compile_runtime(
            section,
            label="model.mpas.initialization",
            workspace=workspace,
            values=values,
            backend=backend,
        )
        check = mpas_artifact_check(
            config,
            name="initialization_state",
            path=product.state,
            default_consumer="model.mpas.forecast",
            expected_time=product.cycle_time,
        )
    except (MpasRuntimeConfigurationError, MpasProductLayoutError, MpasNetcdfContractError) as exc:
        raise MpasInitializationConfigurationError(str(exc)) from exc
    contract = MpasOutputContract(
        required_files=runtime.contract.required_files,
        log_path=runtime.contract.log_path,
        required_log_markers=runtime.contract.required_log_markers,
        netcdf_checks=(*runtime.contract.netcdf_checks, *((check,) if check is not None else ())),
    )
    return MpasInitializationStage(
        product,
        runtime.run_dir,
        contract,
        request=runtime.request,
        backend=backend,
        links=runtime.links,
        templates=runtime.templates,
    )
