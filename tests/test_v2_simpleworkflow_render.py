"""Tests for V2 simpleWorkflow rendering of NMC campaigns."""

from __future__ import annotations

from pathlib import Path

import yaml

from monan_jedi_workflow.cli_v2 import main


def test_campaign_render_simpleworkflow_uses_isolated_stage_contract(tmp_path: Path) -> None:
    """Every rendered task must invoke the public `stage run` CLI contract."""
    output = tmp_path / "nmc.simpleworkflow.yaml"
    workspace = tmp_path / "workspace"
    campaign = Path("examples/v2/bmatrix/nmc_campaign.yaml.example")

    assert main([
        "nmc-campaign",
        "--config", str(campaign),
        "--workspace", str(workspace),
        "--backend", "local",
        "--render-simpleworkflow", str(output),
    ]) == 0

    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    tasks = {task["name"]: task for task in payload["tasks"]}
    assert len(tasks) == 14
    assert tasks["nmc_pairs"]["depends_on"]
    argv = tasks["mpas_init_2026062000"]["argv"]
    assert argv[:3] == ["monan-jedi-workflow-v2", "stage", "run"]
    assert "{resolved_config}" in argv
    assert "{workflow_workspace}" in argv
    assert payload["context"]["backend"] == "local"
