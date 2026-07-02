"""B-matrix workflow specification helpers."""

from collections.abc import Iterable

from ..components.bmatrix.nmc_pairs.stage import NmcPairsStage
from ..components.model.mpas.forecast import MpasForecastStage
from ..core.workflow_spec import StageSpec, WorkflowSpec, WorkflowSpecificationError


def nmc_pairs_workflow(forecasts: Iterable[MpasForecastStage], nmc_pairs: NmcPairsStage) -> WorkflowSpec:
    """Build the MPAS-forecast to NMC-pairs dependency graph.

    The supplied forecast stages must exactly cover the initialization/lead
    products required by the NMC pair plan.
    """
    members = tuple(forecasts)
    expected = {(item.init_time, item.lead_hours) for pair in nmc_pairs.pairs() for item in (pair.older, pair.newer)}
    received = {(item.product.init_time, item.product.lead_hours) for item in members}
    if expected != received:
        raise WorkflowSpecificationError(f"NMC forecast coverage mismatch: missing={sorted(expected - received)}, extra={sorted(received - expected)}.")
    forecasts_spec = tuple(item.spec for item in members)
    handoff = StageSpec(nmc_pairs.spec.name, nmc_pairs.spec.command, needs=tuple(item.name for item in forecasts_spec))
    return WorkflowSpec.from_stages("bmatrix", (*forecasts_spec, handoff), description="MPAS forecasts and NMC BFLOW hand-off.")
