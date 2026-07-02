"""Integration tests for the V2 NMC pairs hand-off stage."""

from __future__ import annotations

from pathlib import Path

import pytest

from monan_jedi_workflow.components.bmatrix.nmc_pairs.stage import NmcPairsStage
from monan_jedi_workflow.components.model.mpas.products import MpasForecastProductLayout, MpasProductLayoutError
from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.core.workflow_spec import WorkflowSpec
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner


def _config(product_root: Path) -> dict[str, object]:
    """Build a complete minimal NMC-pairs configuration fixture."""
    return {
        "model": {
            "mpas": {
                "forecast_products": {
                    "root": str(product_root),
                    "restart_template": "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
                    "state_template": "{init_yyyymmddhh}/f{lead_hours_03d}/mpasout.{mpas_valid_file_time}.nc",
                }
            }
        },
        "bmatrix": {
            "nmc_pairs": {
                "start_valid_time": "2026-06-22T00:00:00Z",
                "end_valid_time": "2026-06-25T00:00:00Z",
                "interval_hours": 24,
                "older_lead_hours": 48,
                "newer_lead_hours": 24,
                "minimum_pairs": 4,
            }
        },
    }


def _create_forecast_products(stage: NmcPairsStage) -> None:
    """Create the exact restart and state files declared by the stage plan."""
    for pair in stage.pairs():
        for forecast in (pair.older, pair.newer):
            forecast.restart.parent.mkdir(parents=True, exist_ok=True)
            forecast.restart.write_bytes(b"restart")
            forecast.state.write_bytes(b"mpas-state")


def test_nmc_pairs_stage_publishes_reusable_bflow_manifest(tmp_path: Path) -> None:
    """A complete forecast set must yield a restart-safe BFLOW hand-off artifact."""
    product_root = tmp_path / "mpas"
    workspace = tmp_path / "workspace"
    context = RunContext("bmatrix", "nmc-smoke", workspace, config=_config(product_root))
    stage = NmcPairsStage.from_context(context)
    _create_forecast_products(stage)

    runner = LocalWorkflowRunner(
        WorkflowSpec.from_stages("bmatrix", [stage.spec]),
        {stage.spec.name: stage},
    )
    result = runner.run(context)

    manifest = workspace / "artifacts/bmatrix/nmc_pairs/bflow-manifest.tsv"
    report = workspace / "artifacts/bmatrix/nmc_pairs/validation-report.json"
    assert len(result) == 1
    assert manifest.is_file()
    assert report.is_file()
    assert manifest.read_text(encoding="utf-8").splitlines()[0] == "valid_time\tf048\tf024"
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == 5
    assert runner.run(context) == ()


def test_mpas_product_layout_rejects_unknown_template_fields(tmp_path: Path) -> None:
    """Undocumented path tokens must fail during configuration construction."""
    with pytest.raises(MpasProductLayoutError, match="unsupported field"):
        MpasForecastProductLayout(
            root=tmp_path,
            restart_template="restart.{unknown}.nc",
            state_template="mpasout.{mpas_valid_file_time}.nc",
        )
