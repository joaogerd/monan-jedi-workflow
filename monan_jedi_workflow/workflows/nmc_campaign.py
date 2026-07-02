"""Planner for V2 MPAS initialization, forecast, and NMC campaigns."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ..components.bmatrix.nmc_pairs.stage import NmcPairsStage
from ..components.model.mpas import (
    MpasForecastStage,
    MpasInitializationStage,
    compile_mpas_forecast,
    compile_mpas_initialization,
    mpas_initialization_context,
    mpas_time_context,
)
from ..components.model.mpas.staging import LinkSpec
from ..components.model.wps import WpsUngribStage, compile_wps_ungrib
from ..core.stage import RunContext, Stage
from ..core.workflow_spec import WorkflowSpec
from ..platforms.base import ExecutionBackend
from .bmatrix_spec import nmc_campaign_workflow


ExecutionBackendFactory = Callable[[str], ExecutionBackend]


@dataclass(frozen=True)
class NmcCampaignPlan:
    """Compiled stages and neutral dependency graph for one NMC campaign."""

    specification: WorkflowSpec
    stages: Mapping[str, Stage]
    initializations: tuple[MpasInitializationStage, ...]
    forecasts: tuple[MpasForecastStage, ...]
    nmc_pairs: NmcPairsStage


def _factory(
    backend: ExecutionBackend | None,
    specific: ExecutionBackendFactory | None,
    label: str,
) -> ExecutionBackendFactory:
    """Resolve one backend factory while preserving the simple local API."""
    if backend is not None and specific is not None:
        raise ValueError(f"Specify either backend or {label}_backend_factory, not both.")
    if specific is not None:
        return specific
    if backend is not None:
        return lambda _stage_name: backend
    raise ValueError(f"Provide backend or {label}_backend_factory.")


def build_nmc_campaign(
    context: RunContext,
    *,
    backend: ExecutionBackend | None = None,
    initialization_backend_factory: ExecutionBackendFactory | None = None,
    forecast_backend_factory: ExecutionBackendFactory | None = None,
) -> NmcCampaignPlan:
    """Compile the configured NMC campaign into executable stages.

    Parameters
    ----------
    context : RunContext
        Resolved B-matrix run context.
    backend : ExecutionBackend | None, default=None
        Shared backend for all MPAS stages. Convenient for local execution.
    initialization_backend_factory : ExecutionBackendFactory | None, default=None
        Factory creating a backend for each initialization stage.
    forecast_backend_factory : ExecutionBackendFactory | None, default=None
        Factory creating a backend for each forecast stage.

    Returns
    -------
    NmcCampaignPlan
        Stage registry and scheduler-neutral dependency graph.

    Notes
    -----
    Each forecast receives the initial state produced for its exact `init_time`
    through the explicit ``initial_state`` template value. Backend factories make
    it possible to assign different JACI resources to initialization and
    forecast work without leaking scheduler details into MPAS components.
    """
    init_factory = _factory(backend, initialization_backend_factory, "initialization")
    forecast_factory = _factory(backend, forecast_backend_factory, "forecast")
    nmc_pairs = NmcPairsStage.from_context(context)
    pairs = nmc_pairs.pairs()
    init_times = tuple(sorted({member.init_time for pair in pairs for member in (pair.older, pair.newer)}))
    initializations = tuple(
        compile_mpas_initialization(
            context.config,
            workspace=context.workspace,
            cycle_time=cycle_time,
            backend=init_factory(
                f"mpas_init_{mpas_initialization_context(cycle_time)['init_yyyymmddhh']}"
            ),
        )
        for cycle_time in init_times
    )
    initial_by_time = {stage.product.cycle_time: stage for stage in initializations}

    forecasts: list[MpasForecastStage] = []
    for pair in pairs:
        for member in (pair.older, pair.newer):
            initialization = initial_by_time[member.init_time]
            init_label = mpas_time_context(member.init_time, member.lead_hours)["init_yyyymmddhh"]
            label = f"mpas_forecast_{init_label}_f{member.lead_hours:03d}"
            forecasts.append(
                compile_mpas_forecast(
                    context.config,
                    workspace=context.workspace,
                    init_time=member.init_time,
                    lead_hours=member.lead_hours,
                    backend=forecast_factory(label),
                    extra_values={"initial_state": str(initialization.product.state)},
                )
            )

    forecast_tuple = tuple(forecasts)
    specification = nmc_campaign_workflow(initializations, forecast_tuple, nmc_pairs)
    stages: dict[str, Stage] = {stage.spec.name: stage for stage in initializations}
    stages.update({stage.spec.name: stage for stage in forecast_tuple})
    stages[nmc_pairs.spec.name] = nmc_pairs
    return NmcCampaignPlan(specification, stages, initializations, forecast_tuple, nmc_pairs)