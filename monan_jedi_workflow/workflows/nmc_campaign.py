"""Planner for V2 MPAS initialization, forecast, and NMC campaigns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..components.bmatrix.nmc_pairs.stage import NmcPairsStage
from ..components.model.mpas import (
    MpasForecastStage,
    MpasInitializationStage,
    compile_mpas_forecast,
    compile_mpas_initialization,
)
from ..core.stage import RunContext, Stage
from ..core.workflow_spec import WorkflowSpec
from ..platforms.base import ExecutionBackend
from .bmatrix_spec import nmc_campaign_workflow


@dataclass(frozen=True)
class NmcCampaignPlan:
    """Compiled stages and neutral dependency graph for one NMC campaign.

    Parameters
    ----------
    specification : WorkflowSpec
        Complete initialization-to-forecast-to-manifest graph.
    stages : Mapping[str, Stage]
        Executable stages keyed by their declared names.
    initializations : tuple[MpasInitializationStage, ...]
        Initialization producers used by the campaign.
    forecasts : tuple[MpasForecastStage, ...]
        Forecast producers used by the NMC pair stage.
    nmc_pairs : NmcPairsStage
        NMC hand-off stage that publishes the BFLOW manifest.
    """

    specification: WorkflowSpec
    stages: Mapping[str, Stage]
    initializations: tuple[MpasInitializationStage, ...]
    forecasts: tuple[MpasForecastStage, ...]
    nmc_pairs: NmcPairsStage


def build_nmc_campaign(context: RunContext, *, backend: ExecutionBackend) -> NmcCampaignPlan:
    """Compile the configured NMC campaign into executable stages.

    Parameters
    ----------
    context : RunContext
        Resolved B-matrix run context.
    backend : ExecutionBackend
        Backend used by all MPAS initialization and forecast stages.

    Returns
    -------
    NmcCampaignPlan
        Stage registry and scheduler-neutral dependency graph.

    Notes
    -----
    Each forecast receives the path of the initial state produced for its exact
    `init_time` through the explicit ``initial_state`` template value. The
    scientific dependency and the artifact path are therefore both declared.
    """
    nmc_pairs = NmcPairsStage.from_context(context)
    pairs = nmc_pairs.pairs()
    init_times = tuple(sorted({member.init_time for pair in pairs for member in (pair.older, pair.newer)}))
    initializations = tuple(
        compile_mpas_initialization(
            context.config,
            workspace=context.workspace,
            cycle_time=cycle_time,
            backend=backend,
        )
        for cycle_time in init_times
    )
    initial_by_time = {stage.product.cycle_time: stage for stage in initializations}

    forecasts: list[MpasForecastStage] = []
    for pair in pairs:
        for member in (pair.older, pair.newer):
            initialization = initial_by_time[member.init_time]
            forecasts.append(
                compile_mpas_forecast(
                    context.config,
                    workspace=context.workspace,
                    init_time=member.init_time,
                    lead_hours=member.lead_hours,
                    backend=backend,
                    extra_values={"initial_state": str(initialization.product.state)},
                )
            )

    forecast_tuple = tuple(forecasts)
    specification = nmc_campaign_workflow(initializations, forecast_tuple, nmc_pairs)
    stages: dict[str, Stage] = {stage.spec.name: stage for stage in initializations}
    stages.update({stage.spec.name: stage for stage in forecast_tuple})
    stages[nmc_pairs.spec.name] = nmc_pairs
    return NmcCampaignPlan(specification, stages, initializations, forecast_tuple, nmc_pairs)
