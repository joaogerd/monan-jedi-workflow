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


def _compile_geog_contract(section: Mapping[str, object]) -> tuple[str | None, tuple[str, ...]]:
    """Compile optional, explicit geographical-data inputs for WPS-backed init."""
    path = section.get("geog_data_path")
    if path is not None and (not isinstance(path, str) or not path):
        raise MpasInitializationConfigurationError("model.mpas.initialization.geog_data_path must be a non-empty string.")
    datasets = section.get("geog_required_datasets", [])
    if not isinstance(datasets, list) or not all(isinstance(item, str) and item for item in datasets):
        raise MpasInitializationConfigurationError(
            "model.mpas.initialization.geog_required_datasets must be a list of non-empty dataset names."
        )
    return path, tuple(datasets)


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
        Stage with explicit runtime, staging, output, geodata, and NetCDF contracts.
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
        geog_data_path, geog_required_datasets = _compile_geog_contract(section)
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
    stage = MpasInitializationStage(
        product,
        runtime.run_dir,
        contract,
        request=runtime.request,
        backend=backend,
        links=runtime.links,
        templates=runtime.templates,
    )
    if geog_data_path is not None:
        stage.values["geog_data_path"] = geog_data_path
        stage.values["geog_required_datasets"] = geog_required_datasets
    return stage
