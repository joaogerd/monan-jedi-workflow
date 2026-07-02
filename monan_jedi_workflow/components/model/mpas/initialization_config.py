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
        Stage with explicit runtime, staging, and output contracts.
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
    except (MpasRuntimeConfigurationError, MpasProductLayoutError) as exc:
        raise MpasInitializationConfigurationError(str(exc)) from exc
    return MpasInitializationStage(
        product,
        runtime.run_dir,
        runtime.contract,
        request=runtime.request,
        backend=backend,
        links=runtime.links,
        templates=runtime.templates,
    )
