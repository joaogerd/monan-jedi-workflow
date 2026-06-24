from __future__ import annotations

import json
import subprocess
from pathlib import Path

from monan_jedi_workflow import pbs
from monan_jedi_workflow.config import ExperimentConfig


def make_config(tmp_path: Path) -> ExperimentConfig:
    return ExperimentConfig(
        root=tmp_path,
        experiment={
            "experiment": {"name": "case"},
            "paths": {"work_root": str(tmp_path), "runtime_dir": "runtime", "rendered_dir": "rendered"},
        },
        runtime={},
        variables={},
        observations={},
        pbs={"pbs": {"log": {"directory": "logs", "filename": "run.${PBS_JOBID}.log"}}},
        validation={},
    )


def test_submit_writes_and_reuses_manifest(monkeypatch, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    runtime_dir = tmp_path / "runtime"
    rendered_dir = tmp_path / "rendered"
    runtime_dir.mkdir()
    rendered_dir.mkdir()
    (rendered_dir / "case.pbs").write_text("#!/bin/bash\n", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="123.server\n", stderr="")

    monkeypatch.setattr(pbs.subprocess, "run", fake_run)
    submission = pbs.submit(config)
    assert submission.job_id == "123.server"
    assert calls == [["qsub", str(rendered_dir / "case.pbs")]]
    assert json.loads(submission.manifest_path.read_text())["state"] == "submitted"
    assert pbs.submit(config).reused is True
    assert len(calls) == 1


def test_wait_records_scheduler_completion(monkeypatch, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    path = pbs.manifest_path(config)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"job_id": "123.server", "state": "submitted"}))
    statuses = iter([(True, "R"), (False, None)])
    monkeypatch.setattr(pbs, "query", lambda job_id: next(statuses))
    monkeypatch.setattr(pbs.time, "sleep", lambda seconds: None)
    assert pbs.wait(config, poll_seconds=1) == "R"
    assert json.loads(path.read_text())["state"] == "scheduler-finished"
