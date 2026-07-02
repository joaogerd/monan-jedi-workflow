"""B-matrix workflow specification helpers."""

from collections.abc import Iterable

from ..components.bmatrix.nmc_pairs.stage import NmcPairsStage
from ..components.model.mpas.forecast import MpasForecastStage
from ..components.model.mpas.initialization import MpasInitializationStage
from ..core.workflow_spec import StageSpec, WorkflowSpec, WorkflowSpecificationError


def _spec_with_needs(spec: StageSpec, needs: tuple[str, ...]) -> StageSpec:
    """Copy one stage declaration with explicit dependency names."""
    return StageSpec(spec.name, spec.command, needs=needs, description=spec.description)


def nmc_pairs_workflow(
    forecasts: Iterable[MpasForecastStage],
    nmc_pairs: NmcPairsStage,
) -> WorkflowSpec:
    """Build the MPAS-forecast to NMC-pairs dependency graph.

    The supplied forecast stages must exactly cover the initialization/lead
    products required by the NMC pair plan.
    """
    members = tuple(forecasts)
    expected = {(item.init_time, item.lead_hours) for pair in nmc_pairs.pairs() for item in (pair.older, pair.newer)}
    received = {(item.product.init_time, item.product.lead_hours) for item in members}
    if expected != received:
        raise WorkflowSpecificationError(
            f"NMC forecast coverage mismatch: missing={sorted(expected - received)}, extra={sorted(received - expected)}."
        )
    forecasts_spec = tuple(item.spec for item in members)
    handoff = _spec_with_needs(nmc_pairs.spec, tuple(item.name for item in forecasts_spec))
    return WorkflowSpec.from_stages(
        "bmatrix",
        (*forecasts_spec, handoff),
        description="MPAS forecasts and NMC BFLOW hand-off.",
    )


def nmc_campaign_workflow(
    initializations: Iterable[MpasInitializationStage],
    forecasts: Iterable[MpasForecastStage],
    nmc_pairs: NmcPairsStage,
) -> WorkflowSpec:
    """Build an initialization-to-forecast-to-NMC workflow graph.

    Parameters
    ----------
    initializations : Iterable[MpasInitializationStage]
        Initialization stages that create the initial states for all forecasts.
    forecasts : Iterable[MpasForecastStage]
        Forecast stages required by the configured NMC pair plan.
    nmc_pairs : NmcPairsStage
        Manifest publication stage.

    Returns
    -------
    WorkflowSpec
        Scheduler-neutral graph with `init -> forecast -> nmc_pairs` edges.

    Raises
    ------
    WorkflowSpecificationError
        Raised when forecast coverage is incomplete, initializations are
        duplicated, or a forecast has no initialization stage.
    """
    init_members = tuple(initializations)
    forecast_members = tuple(forecasts)
    forecast_spec = nmc_pairs_workflow(forecast_members, nmc_pairs)
    by_time = {stage.product.cycle_time: stage for stage in init_members}
    if len(by_time) != len(init_members):
        raise WorkflowSpecificationError("MPAS initialization stages must have unique cycle times.")

    required_times = {stage.product.init_time for stage in forecast_members}
    available_times = set(by_time)
    if required_times != available_times:
        raise WorkflowSpecificationError(
            f"MPAS initialization coverage mismatch: missing={sorted(required_times - available_times)}, "
            f"extra={sorted(available_times - required_times)}."
        )

    init_specs = tuple(stage.spec for stage in init_members)
    updated_forecasts = tuple(
        _spec_with_needs(stage.spec, (by_time[stage.product.init_time].spec.name,))
        for stage in forecast_members
    )
    handoff = _spec_with_needs(nmc_pairs.spec, tuple(stage.name for stage in updated_forecasts))
    return WorkflowSpec.from_stages(
        "bmatrix",
        (*init_specs, *updated_forecasts, handoff),
        description="MPAS initialization, forecasts, and NMC BFLOW hand-off.",
    )
