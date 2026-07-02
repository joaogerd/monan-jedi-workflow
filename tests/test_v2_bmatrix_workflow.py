"""Tests for V2 B-matrix workflow composition."""

from pathlib import Path

import pytest

from monan_jedi_workflow.components.bmatrix.nmc_pairs.stage import NmcPairsStage
from monan_jedi_workflow.components.model.mpas import MpasForecastStage, MpasOutputContract
from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.core.workflow_spec import WorkflowSpecificationError
from monan_jedi_workflow.workflows.bmatrix_spec import nmc_pairs_workflow


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


def test_nmc_workflow_links_all_forecasts_to_manifest_stage(tmp_path: Path) -> None:
    """NMC publication must depend on every planned f048 and f024 forecast."""
    context = _context(tmp_path)
    nmc = NmcPairsStage.from_context(context)
    forecasts = [MpasForecastStage(item, tmp_path / "runs" / str(index), MpasOutputContract(())) for index, pair in enumerate(nmc.pairs()) for item in (pair.older, pair.newer)]
    spec = nmc_pairs_workflow(forecasts, nmc)
    assert spec.stage("nmc_pairs").needs == tuple(stage.spec.name for stage in forecasts)
    assert len(spec.stages) == 9


def test_nmc_workflow_rejects_incomplete_forecast_coverage(tmp_path: Path) -> None:
    """A missing f024 or f048 stage must fail before scheduler rendering."""
    context = _context(tmp_path)
    nmc = NmcPairsStage.from_context(context)
    pair = nmc.pairs()[0]
    forecast = MpasForecastStage(pair.older, tmp_path / "run", MpasOutputContract(()))
    with pytest.raises(WorkflowSpecificationError, match="coverage mismatch"):
        nmc_pairs_workflow([forecast], nmc)
