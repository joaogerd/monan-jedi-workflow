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


def _require_string(value: object, label: str) -> str:
    """Require one non-empty string with a YAML-specific error message."""
    if not isinstance(value, str) or not value:
        raise MpasInitializationConfigurationError(f"{label} must be a non-empty string.")
    return value


def _compile_static_fields(section: Mapping[str, object], runtime_links: tuple[object, ...]) -> dict[str, object]:
    """Compile the declared static-fields strategy for WPS-backed initialization."""
    if section.get("wps_input") is None:
        return {}
    fields = require_mapping(section.get("static_fields"), "model.mpas.initialization.static_fields")
    mode = _require_string(fields.get("mode"), "model.mpas.initialization.static_fields.mode")

    if mode == "invariant":
        source = Path(_require_string(fields.get("source"), "model.mpas.initialization.static_fields.source"))
        target = Path(_require_string(fields.get("target"), "model.mpas.initialization.static_fields.target"))
        if not source.is_absolute() or not source.name.endswith(".invariant.nc"):
            raise MpasInitializationConfigurationError(
                "model.mpas.initialization.static_fields.source must be an absolute '.invariant.nc' path."
            )
        if target.is_absolute() or target.parent != Path(".") or not target.name.endswith(".grid.nc"):
            raise MpasInitializationConfigurationError(
                "model.mpas.initialization.static_fields.target must be a run-local '*.grid.nc' filename."
            )
        if not any(
            getattr(link, "source", None) == source and getattr(link, "target", None).name == target.name
            for link in runtime_links
        ):
            raise MpasInitializationConfigurationError(
                "model.mpas.initialization.static_fields invariant source/target must also be declared in links."
            )
        return {
            "static_fields_mode": mode,
            "static_fields_source": str(source),
            "static_fields_target": target.name,
        }

    if mode == "interpolate_geography":
        root = Path(
            _require_string(
                fields.get("geog_data_path"),
                "model.mpas.initialization.static_fields.geog_data_path",
            )
        )
        datasets = fields.get("geog_required_datasets")
        if not root.is_absolute():
            raise MpasInitializationConfigurationError(
                "model.mpas.initialization.static_fields.geog_data_path must be absolute."
            )
        if not isinstance(datasets, list) or not datasets or not all(isinstance(item, str) and item for item in datasets):
            raise MpasInitializationConfigurationError(
                "model.mpas.initialization.static_fields.geog_required_datasets must be a non-empty string list."
            )
        return {
            "static_fields_mode": mode,
            "geog_data_path": str(root),
            "geog_required_datasets": tuple(datasets),
        }

    raise MpasInitializationConfigurationError(
        "model.mpas.initialization.static_fields.mode must be 'invariant' or 'interpolate_geography'."
    )


def compile_mpas_initialization(
    config: Mapping[str, object],
    *,
    workspace: Path,
    cycle_time: str,
    backend: ExecutionBackend,
) -> MpasInitializationStage:
    """Compile one configured MPAS initialization into an executable stage."""
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
        static_values = _compile_static_fields(section, runtime.links)
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
    stage.values.update(static_values)
    return stage
