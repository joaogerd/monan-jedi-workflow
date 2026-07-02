"""B-matrix workflow specification helpers."""

from collections.abc import Iterable

from ..components.bmatrix.nmc_pairs.stage import NmcPairsStage
from ..components.model.mpas.forecast import MpasForecastStage
from ..components.model.mpas.initialization import MpasInitializationStage
from ..components.model.wps import WpsUngribStage
from ..core.workflow_spec import StageSpec, WorkflowSpec, WorkflowSpecificationError


# WPS producer dependencies are introduced by the V2 NMC planner.
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
    wps_stages: Iterable[WpsUngribStage] = (),
) -> WorkflowSpec:
    """Build an initialization-to-forecast-to-NMC workflow graph.

    WPS stages are optional for generic unit fixtures, but when supplied they
    must cover every initialization time and become direct init dependencies.
    """
    init_members = tuple(initializations)
    forecast_members = tuple(forecasts)
    wps_members = tuple(wps_stages)
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
    wps_by_time = {stage.product.init_time: stage for stage in wps_members}
    if wps_members and set(wps_by_time) != available_times:
        raise WorkflowSpecificationError("WPS stages must cover exactly the MPAS initialization times.")

    init_specs = tuple(
        _spec_with_needs(stage.spec, (wps_by_time[stage.product.cycle_time].spec.name,))
        if wps_members else stage.spec
        for stage in init_members
    )
    init_spec_by_name = {item.name: item for item in init_specs}
    updated_forecasts = tuple(
        _spec_with_needs(stage.spec, (init_spec_by_name[by_time[stage.product.init_time].spec.name].name,))
        for stage in forecast_members
    )
    handoff = _spec_with_needs(nmc_pairs.spec, tuple(stage.name for stage in updated_forecasts))
    return WorkflowSpec.from_stages(
        "bmatrix",
        (*(stage.spec for stage in wps_members), *init_specs, *updated_forecasts, handoff),
        description="WPS, MPAS initialization, forecasts, and NMC BFLOW hand-off.",
    )
