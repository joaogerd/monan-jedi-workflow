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
    wps_ungrib: tuple[WpsUngribStage, ...] = ()


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


def _has_wps(config: Mapping[str, object]) -> bool:
    """Return whether this case declares the WPS `ungrib` producer."""
    model = config.get("model")
    return isinstance(model, Mapping) and isinstance(model.get("wps"), Mapping)


def _partition_prefix(initialization: MpasInitializationStage) -> str | None:
    """Return the declared MPAS decomposition prefix when one is available.

    Generic planning and dry-run fixtures may intentionally omit static mesh
    artifacts. A real WPS-backed initialization still fails during preparation
    when it renders a namelist but lacks this required decomposition prefix.
    """
    for link in initialization.links:
        name = link.target.name
        if ".graph.info.part." not in name:
            continue
        stem, separator, ranks = name.rpartition(".")
        if separator and ranks.isdigit():
            return f"{stem}."
    return None


def _attach_wps_file(config: Mapping[str, object], initialization: MpasInitializationStage, forcing: WpsUngribStage) -> None:
    """Stage and expose the upstream WPS FILE product for MPAS initialization."""
    model = config.get("model")
    if not isinstance(model, Mapping) or not isinstance(model.get("mpas"), Mapping):
        raise ValueError("model.mpas is required to bind a WPS forcing product.")
    section = model["mpas"].get("initialization")
    if not isinstance(section, Mapping) or not isinstance(section.get("wps_input"), Mapping):
        raise ValueError("model.mpas.initialization.wps_input is required when model.wps is declared.")
    target = section["wps_input"].get("target")
    if not isinstance(target, str) or not target:
        raise ValueError("model.mpas.initialization.wps_input.target must be a non-empty string.")
    values = mpas_initialization_context(initialization.product.cycle_time)
    try:
        candidate = Path(target.format_map(values))
    except KeyError as exc:
        raise ValueError(f"WPS input target uses unknown placeholder: {exc.args[0]}") from exc
    if not candidate.name.startswith("FILE:"):
        raise ValueError("MPAS initialization WPS input target must use the FILE: prefix.")
    path = candidate if candidate.is_absolute() else initialization.run_dir / candidate
    initialization.links = (*initialization.links, LinkSpec(forcing.product.intermediate, path))
    initialization.values["met_input"] = str(forcing.product.intermediate)
    initialization.values["met_input_filename"] = path.name
    prefix = _partition_prefix(initialization)
    if prefix is not None:
        initialization.values["decomposition_prefix"] = prefix


def build_nmc_campaign(
    context: RunContext,
    *,
    backend: ExecutionBackend | None = None,
    wps_backend_factory: ExecutionBackendFactory | None = None,
    initialization_backend_factory: ExecutionBackendFactory | None = None,
    forecast_backend_factory: ExecutionBackendFactory | None = None,
) -> NmcCampaignPlan:
    """Compile the configured NMC campaign into executable stages.

    WPS, initialization, and forecast backends are independently configurable so
    serial `ungrib` does not inherit the MPI allocation of MPAS initialization.
    """
    init_factory = _factory(backend, initialization_backend_factory, "initialization")
    forecast_factory = _factory(backend, forecast_backend_factory, "forecast")
    wps_factory = _factory(backend, wps_backend_factory, "wps") if wps_backend_factory else init_factory
    nmc_pairs = NmcPairsStage.from_context(context)
    pairs = nmc_pairs.pairs()
    init_times = tuple(sorted({member.init_time for pair in pairs for member in (pair.older, pair.newer)}))
    wps_stages = tuple(
        compile_wps_ungrib(
            context.config,
            workspace=context.workspace,
            init_time=cycle_time,
            backend=wps_factory(f"wps_ungrib_{mpas_initialization_context(cycle_time)['init_yyyymmddhh']}"),
        )
        for cycle_time in init_times
    ) if _has_wps(context.config) else ()
    wps_by_time = {stage.product.init_time: stage for stage in wps_stages}

    initialized: list[MpasInitializationStage] = []
    for cycle_time in init_times:
        stage = compile_mpas_initialization(
            context.config,
            workspace=context.workspace,
            cycle_time=cycle_time,
            backend=init_factory(f"mpas_init_{mpas_initialization_context(cycle_time)['init_yyyymmddhh']}"),
        )
        if wps_stages:
            _attach_wps_file(context.config, stage, wps_by_time[cycle_time])
        initialized.append(stage)
    initializations = tuple(initialized)
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
    specification = nmc_campaign_workflow(initializations, forecast_tuple, nmc_pairs, wps_stages)
    stages: dict[str, Stage] = {stage.spec.name: stage for stage in wps_stages}
    stages.update({stage.spec.name: stage for stage in initializations})
    stages.update({stage.spec.name: stage for stage in forecast_tuple})
    stages[nmc_pairs.spec.name] = nmc_pairs
    return NmcCampaignPlan(specification, stages, initializations, forecast_tuple, nmc_pairs, wps_stages)
