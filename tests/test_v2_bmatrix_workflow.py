"""Tests for V2 B-matrix workflow composition."""

from pathlib import Path

import pytest

from monan_jedi_workflow.components.bmatrix.nmc_pairs.stage import NmcPairsStage
from monan_jedi_workflow.components.model.mpas import (
    MpasForecastStage,
    MpasInitializationProduct,
    MpasInitializationStage,
    MpasOutputContract,
)
from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.core.workflow_spec import WorkflowSpecificationError
from monan_jedi_workflow.workflows.bmatrix_spec import nmc_campaign_workflow, nmc_pairs_workflow


def _context(root: Path) -> RunContext:
    config = {
        "model": {"mpas": {"forecast_products": {
            "root": str(root),
            "restart_template": "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
            "state_template": "{init_yyyymmddhh}/f{lead_hours_03d}/mpasout.{mpas_valid_file_time}.nc",
        }}},
        "bmatrix": {"nmc_pairs": {
            "start_valid_time": "2026-06-22T00:00:00Z",
            "end_valid_time": "2026-06-25T00:00:00Z",
        }},
    }
    return RunContext("bmatrix", "test", root / "workspace", config=config)


def _forecasts(nmc: NmcPairsStage, root: Path) -> list[MpasForecastStage]:
    return [
        MpasForecastStage(item, root / "runs" / str(index), MpasOutputContract(()))
        for index, pair in enumerate(nmc.pairs())
        for item in (pair.older, pair.newer)
    ]


def _initializations(forecasts: list[MpasForecastStage], root: Path) -> list[MpasInitializationStage]:
    unique = sorted({stage.product.init_time for stage in forecasts})
    return [
        MpasInitializationStage(
            MpasInitializationProduct(value, root / "initial" / f"{index}.nc"),
            root / "init-runs" / str(index),
            MpasOutputContract(()),
        )
        for index, value in enumerate(unique)
    ]


def test_nmc_workflow_links_all_forecasts_to_manifest_stage(tmp_path: Path) -> None:
    """NMC publication must depend on every planned f048 and f024 forecast."""
    nmc = NmcPairsStage.from_context(_context(tmp_path))
    forecasts = _forecasts(nmc, tmp_path)
    spec = nmc_pairs_workflow(forecasts, nmc)
    assert spec.stage("nmc_pairs").needs == tuple(stage.spec.name for stage in forecasts)
    assert len(spec.stages) == 9


def test_nmc_campaign_links_initialization_forecast_and_handoff(tmp_path: Path) -> None:
    """Each forecast must depend on its matching initialization stage."""
    nmc = NmcPairsStage.from_context(_context(tmp_path))
    forecasts = _forecasts(nmc, tmp_path)
    initializations = _initializations(forecasts, tmp_path)
    spec = nmc_campaign_workflow(initializations, forecasts, nmc)

    assert len(initializations) == 5
    assert len(spec.stages) == 14
    by_time = {stage.product.cycle_time: stage.spec.name for stage in initializations}
    for forecast in forecasts:
        assert spec.stage(forecast.spec.name).needs == (by_time[forecast.product.init_time],)


def test_nmc_workflow_rejects_incomplete_forecast_coverage(tmp_path: Path) -> None:
    """A missing f024 or f048 stage must fail before scheduler rendering."""
    nmc = NmcPairsStage.from_context(_context(tmp_path))
    forecast = MpasForecastStage(nmc.pairs()[0].older, tmp_path / "run", MpasOutputContract(()))
    with pytest.raises(WorkflowSpecificationError, match="coverage mismatch"):
        nmc_pairs_workflow([forecast], nmc)


def test_nmc_campaign_rejects_missing_initialization(tmp_path: Path) -> None:
    """A forecast cannot enter the DAG without its initialization producer."""
    nmc = NmcPairsStage.from_context(_context(tmp_path))
    forecasts = _forecasts(nmc, tmp_path)
    initializations = _initializations(forecasts, tmp_path)[:-1]
    with pytest.raises(WorkflowSpecificationError, match="initialization coverage mismatch"):
        nmc_campaign_workflow(initializations, forecasts, nmc)
