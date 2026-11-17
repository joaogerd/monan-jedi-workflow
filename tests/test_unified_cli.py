"""Public CLI is seven independent executable names, not a wrapper prefix."""
import sys
from pathlib import Path
import yaml
import pytest

from monan_jedi_workflow import command_entrypoints as entry
from monan_jedi_workflow import unified_cli as experiment_impl


def test_public_package_entrypoints():
    from pathlib import Path
    data = Path("pyproject.toml").read_text().split("[project.scripts]", 1)[1].split("[", 1)[0]
    scripts = {line.split("=", 1)[0].strip() for line in data.splitlines() if "=" in line}
    for name in ("experiment", "wps", "obs", "mpas", "jedi", "diagnostic", "diagnose"):
        assert name in scripts
    assert "monan-workflow" not in scripts


def test_experiment_direct_cli_creates_date_configured_campaign(tmp_path, monkeypatch):
    destination = tmp_path / "another-date"
    monkeypatch.setattr(sys, "argv", ["experiment", "create", str(destination),
                                     "--start", "2024-02-29T00:00:00Z",
                                     "--mode", "cold"])
    assert entry.experiment() == 0
    campaign = yaml.safe_load((destination / "campaign.yaml").read_text())
    assert campaign["calendar"]["start"] == "2024-02-29T00:00:00Z"
    assert campaign["initialization"][0]["cycle"] == "2024-02-28T18:00:00Z"


def test_experiment_warm_refused_without_writing(tmp_path, monkeypatch, capsys):
    root = tmp_path / "warm"
    monkeypatch.setattr(sys, "argv", ["experiment", "create", str(root),
                                     "--mode", "warm"])
    assert entry.experiment() == 2
    assert not root.exists()
    assert "não implementado" in capsys.readouterr().err.lower()


def test_experiment_plan_proxies_simpleworkflow(monkeypatch):
    from subprocess import CompletedProcess
    seen = []
    monkeypatch.setattr(experiment_impl.subprocess, "run",
                        lambda argv, **kw: seen.append((argv, kw)) or CompletedProcess(argv, 0))
    monkeypatch.setattr(sys, "argv", ["experiment", "plan", "workflow.yaml"])
    assert entry.experiment() == 0
    assert seen == [(["swf", "plan", "workflow.yaml"], {"check": False})]


def test_wps_direct_entrypoint(monkeypatch):
    from monan_jedi_workflow import cli_frontend
    seen = []
    monkeypatch.setattr(cli_frontend, "main", lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", ["wps", "prepare", "science/initialization",
                                     "--cycle", "2024-02-28T18:00:00Z"])
    assert entry.wps() == 0
    assert seen == [["wps-prepare", "science/initialization", "--cycle",
                     "2024-02-28T18:00:00Z"]]


def test_diagnostic_direct_entrypoint(monkeypatch):
    from monan_jedi_workflow import platform_cli
    calls = []
    monkeypatch.setattr(platform_cli, "main", lambda app, argv: calls.append((app, argv)) or 0)
    monkeypatch.setattr(sys, "argv", ["diagnostic", "status", "experiment.yaml",
                                     "--cycle", "2024-02-29T00:00:00Z"])
    assert entry.diagnostic() == 0
    assert calls == [("diagnostics", ["status", "experiment.yaml",
                                      "--cycle", "2024-02-29T00:00:00Z"])]


def test_diagnose_direct_entrypoint(monkeypatch):
    from monan_jedi_workflow import diagnostics
    calls = []
    monkeypatch.setattr(diagnostics, "main", lambda argv: calls.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", ["diagnose", ".", "--no-pbs"])
    assert entry.diagnose() == 0
    assert calls == [[".", "--no-pbs"]]


def test_all_exported_tasks_use_direct_domain_commands(tmp_path, monkeypatch):
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
    workflow = yaml.safe_load((root / "workflow.yaml").read_text())
    stages = workflow["initialization"]["tasks"] + workflow["tasks"]
    assert len(stages) == 24
    assert set(t["argv"][0] for t in stages) == {"wps", "mpas", "obs", "jedi"}
    assert any(t["argv"][:2] == ["wps", "run"] for t in stages)
    assert any(t["argv"][:3] == ["obs", "convert", "run"] for t in stages)
    assert any(t["argv"][:2] == ["jedi", "run"] for t in stages)



def test_experiment_site_save_dispatches_to_workspace_profile(monkeypatch, tmp_path):
    from monan_jedi_workflow import experiment_environment
    called = []
    monkeypatch.setattr(experiment_environment, "save_project_site",
                        lambda path: called.append(path) or tmp_path / "site.yaml")
    monkeypatch.setattr(sys, "argv", ["experiment", "site", "save"])
    assert entry.experiment() == 0
    assert called == [Path.cwd()]


def test_experiment_site_save_rejects_invalid_action(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["experiment", "site", "overwrite"])
    assert entry.experiment() == 2



def test_experiment_site_init_disambiguates_stack_without_old_case(monkeypatch, tmp_path):
    from monan_jedi_workflow import experiment_environment
    calls = []
    stack = tmp_path / "stack"
    install = tmp_path / "install"
    monkeypatch.setattr(
        experiment_environment, "initialize_site",
        lambda root, *, stack=None, install=None: (
            calls.append((root, stack, install)) or tmp_path / "site.yaml"
        ),
    )
    monkeypatch.setattr(
        sys, "argv",
        ["experiment", "site", "init", "--stack", str(stack),
         "--install", str(install)],
    )
    assert entry.experiment() == 0
    assert calls == [(Path.cwd(), stack, install)]
