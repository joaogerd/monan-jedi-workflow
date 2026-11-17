"""The single public executable dispatches to independent domain apps."""
from pathlib import Path
import json
import subprocess
import sys
import yaml

import pytest

import monan_jedi_workflow.unified_cli as unified


def test_help_lists_the_seven_public_domains(capsys):
    assert unified.main(["--help"]) == 0
    help_text = capsys.readouterr().out
    for command in ("experiment", "wps", "obs", "mpas", "jedi",
                    "diagnostic", "diagnose"):
        assert command in help_text


@pytest.mark.parametrize("args,app,forwarded", [
    (["obs", "convert", "status", "exp.yaml", "--cycle", "2024-02-29T00:00:00Z"],
     "obs", ["convert", "status", "exp.yaml", "--cycle", "2024-02-29T00:00:00Z"]),
    (["mpas", "init", "prepare", "init.yaml", "--cycle", "2024-02-28T18:00:00Z"],
     "mpas", ["init", "prepare", "init.yaml", "--cycle", "2024-02-28T18:00:00Z"]),
    (["jedi", "validate", "exp.yaml", "--cycle", "2024-02-29T06:00:00Z"],
     "jedi", ["validate", "exp.yaml", "--cycle", "2024-02-29T06:00:00Z"]),
    (["diagnostic", "run", "exp.yaml", "--cycle", "2024-02-29T06:00:00Z"],
     "diagnostics", ["run", "exp.yaml", "--cycle", "2024-02-29T06:00:00Z"]),
    (["experiment", "check", "campaign.yaml"], "campaign", ["check", "campaign.yaml"]),
])
def test_domain_dispatch_preserves_args(monkeypatch, args, app, forwarded):
    called = []
    monkeypatch.setattr(unified, "_domain", lambda a, b: called.append((a, b)) or 0)
    assert unified.main(args) == 0
    assert called == [(app, forwarded)]


def test_wps_dispatch_preserves_legacy_native_stage(monkeypatch):
    from monan_jedi_workflow import cli_frontend
    called = []
    monkeypatch.setattr(cli_frontend, "main", lambda args: called.append(args) or 0)
    assert unified.main(["wps", "prepare", "/config", "--cycle", "2024-02-28T18:00:00Z"]) == 0
    assert called == [["wps-prepare", "/config", "--cycle", "2024-02-28T18:00:00Z"]]


def test_experiment_start_arbitrary_date_from_one_executable(tmp_path):
    destination = tmp_path / "another-date"
    assert unified.main([
        "experiment", "create", str(destination),
        "--start", "2024-02-29T00:00:00Z", "--mode", "cold",
    ]) == 0
    campaign = yaml.safe_load((destination / "campaign.yaml").read_text())
    assert campaign["calendar"]["start"] == "2024-02-29T00:00:00Z"
    assert campaign["initialization"][0]["cycle"] == "2024-02-28T18:00:00Z"


def test_unimplemented_warm_start_refuses_without_side_effects(tmp_path, capsys):
    destination = tmp_path / "cannot-warm"
    assert unified.main([
        "experiment", "create", str(destination),
        "--start", "2024-02-29T00:00:00Z", "--mode", "warm",
    ]) == 2
    assert not destination.exists()
    assert "não implementado" in capsys.readouterr().err.lower()


def test_engine_proxy_does_not_invent_another_workflow_engine(monkeypatch):
    called = []
    monkeypatch.setattr(
        unified.subprocess, "run",
        lambda argv, **kw: called.append((argv, kw)) or
            subprocess.CompletedProcess(argv, 17),
    )
    assert unified.main(["experiment", "run", "workflow.yaml", "--ui", "plain"]) == 17
    assert called == [(["swf", "run", "workflow.yaml", "--ui", "plain"], {"check": False})]


def test_exported_tasks_use_single_binary_not_legacy_entrypoints(tmp_path, monkeypatch):
    from monan_jedi_workflow.experiment_start import create_experiment
    from monan_jedi_workflow.platform_campaign import campaign_action
    from monan_jedi_workflow.domain_cli import parse_request

    for name in ("MONAN_JEDI_INSTALL_ROOT", "STACK_ROOT", "MONAN_INPUT_ROOT",
                 "MONAN_MESH_ROOT", "MONAN_PHYSICS_ROOT", "MONAN_BMATRIX_ROOT",
                 "MONAN_LIBFABRIC_ROOT", "MONAN_GFS_ROOT"):
        monkeypatch.setenv(name, str(tmp_path / name))
    root = tmp_path / "new"
    create_experiment(root, start="2024-02-29T00:00:00Z")
    campaign_action(parse_request("campaign", ["export", str(root / "campaign.yaml")]))
    config = yaml.safe_load((root / "workflow.yaml").read_text())
    stages = config["initialization"]["tasks"] + config["tasks"]
    assert len(stages) == 24
    assert all(task["argv"][0] == "monan-workflow" for task in stages)
    assert any(task["argv"][:3] == ["monan-workflow", "wps", "run"] for task in stages)
    assert any(task["argv"][:4] == ["monan-workflow", "obs", "convert", "run"] for task in stages)
    assert any(task["argv"][:3] == ["monan-workflow", "jedi", "run"] for task in stages)
