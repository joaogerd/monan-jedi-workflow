"""PBS exit status is authoritative for MPAS Init, not terminal job state."""
from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest

import monan_jedi_workflow.init_stage as stage


@pytest.mark.parametrize("exit_status,expected_state,raises", [
    (0, "scheduler-finished", False),
    (271, "scheduler-failed", True),
])
def test_init_wait_checks_pbs_exit_status(monkeypatch, tmp_path, exit_status, expected_state, raises):
    run = SimpleNamespace(
        run_dir=tmp_path,
        manifest_path=tmp_path / "mpas-init.json",
        cycle=SimpleNamespace(cycle_time="2025-08-31T18:00:00Z"),
    )
    monkeypatch.setattr(stage, "_load", lambda *args: run)
    monkeypatch.setattr(stage, "_read", lambda *args: {"job_id": "826106.pbs-ha"})
    saved = []
    monkeypatch.setattr(stage, "_save", lambda _run, value: saved.append(value.copy()))
    monkeypatch.setattr(stage, "query", lambda job: (True, "F"))
    commands = []
    def fake_run(argv, **kwargs):
        commands.append(argv)
        return subprocess.CompletedProcess(
            argv, 0,
            f"Job Id: 826106.pbs-ha\n    job_state = F\n    Exit_status = {exit_status}\n", ""
        )
    monkeypatch.setattr(stage.subprocess, "run", fake_run)
    if raises:
        with pytest.raises(stage.PBSError, match="Exit_status=271"):
            stage.wait_mpas_init(tmp_path, run.cycle.cycle_time)
    else:
        stage.wait_mpas_init(tmp_path, run.cycle.cycle_time)
    assert commands == [["qstat", "-x", "-f", "826106.pbs-ha"]]
    assert saved[-1]["state"] == expected_state
    assert saved[-1]["pbs_exit_status"] == exit_status


def test_init_wait_refuses_missing_pbs_history(monkeypatch, tmp_path):
    run = SimpleNamespace(run_dir=tmp_path, manifest_path=tmp_path / "mpas-init.json")
    monkeypatch.setattr(stage, "_load", lambda *args: run)
    monkeypatch.setattr(stage, "_read", lambda *args: {"job_id": "826106.pbs-ha"})
    saved = []
    monkeypatch.setattr(stage, "_save", lambda _run, value: saved.append(value.copy()))
    monkeypatch.setattr(stage, "query", lambda job: (False, None))
    monkeypatch.setattr(stage.subprocess, "run", lambda argv, **kwargs:
                        subprocess.CompletedProcess(argv, 35, "", "Unknown Job Id"))
    with pytest.raises(stage.PBSError, match="Exit_status could not be verified"):
        stage.wait_mpas_init(tmp_path, "2025-08-31T18:00:00Z")
    assert saved[-1]["state"] == "scheduler-unconfirmed"
