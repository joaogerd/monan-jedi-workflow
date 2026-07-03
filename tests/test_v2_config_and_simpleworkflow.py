"""Tests for V2 configuration and simpleWorkflow adaptation."""

from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.core.config import resolve_configuration, write_resolved_configuration
from monan_jedi_workflow.core.workflow_spec import StageSpec, WorkflowSpec
from monan_jedi_workflow.orchestration.simpleworkflow import render_workflow


def test_configuration_layers_merge_without_mutating_lower_precedence(tmp_path: Path) -> None:
    """Site, profile, and case layers must have deterministic precedence."""
    site = tmp_path / "site.yaml"
    profile = tmp_path / "profile.yaml"
    case = tmp_path / "case.yaml"
    site.write_text("platform:\n  queue: research\nmodel:\n  nproc: 128\n", encoding="utf-8")
    profile.write_text("model:\n  mesh: x1.10242\n", encoding="utf-8")
    case.write_text("case:\n  name: smoke\nplatform:\n  queue: mini\n", encoding="utf-8")

    resolved = resolve_configuration([site, profile, case])
    output = write_resolved_configuration(tmp_path / "resolved-config.yaml", resolved)

    assert resolved["platform"]["queue"] == "mini"
    assert resolved["model"] == {"nproc": 128, "mesh": "x1.10242"}
    assert "name: smoke" in output.read_text(encoding="utf-8")


def test_simpleworkflow_renderer_preserves_stage_dependencies() -> None:
    """The adapter must render the neutral DAG using simpleWorkflow fields."""
    specification = WorkflowSpec.from_stages(
        "bmatrix",
        [
            StageSpec("nmc_pairs", "bmatrix.nmc_pairs"),
            StageSpec("bflow", "bmatrix.bflow", needs=("nmc_pairs",)),
        ],
    )

    rendered = render_workflow(
        specification,
        context={"case_file": "case.yaml"},
        argv_for_stage=lambda stage: (
            "monan-jedi-workflow",
            "stage",
            "run",
            "--stage",
            stage.name,
            "--case",
            "{case_file}",
        ),
    )

    assert rendered["workflow"]["name"] == "bmatrix"
    assert rendered["tasks"][0]["name"] == "nmc_pairs"
    assert rendered["tasks"][1]["depends_on"] == ["nmc_pairs"]
    assert rendered["tasks"][1]["argv"][0] == "monan-jedi-workflow"
