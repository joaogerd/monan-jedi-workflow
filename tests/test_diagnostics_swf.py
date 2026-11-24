import json
import sqlite3
from pathlib import Path

from monan_jedi_workflow.diagnostics import diagnose, _workflow_failure


def test_doctor_reports_swf_root_cause_and_does_not_mutate_state(tmp_path):
    state = tmp_path / ".simpleworkflow"
    state.mkdir()
    dbpath = state / "state.sqlite3"
    with sqlite3.connect(dbpath) as connection:
        connection.execute(
            "CREATE TABLE task_state (task TEXT, status TEXT, reason TEXT, "
            "attempt_path TEXT, updated_at TEXT)"
        )
        connection.executemany(
            "INSERT INTO task_state VALUES (?, ?, ?, ?, ?)",
            [
                ("c00004_obs_convert_prepare", "FAILED", "return code 1", None, "2026-11-20T19:46:00Z"),
                ("c00004_obs_convert_run", "BLOCKED", "dependency failed", None, "2026-11-20T19:46:01Z"),
            ],
        )
    log = (state / "runs" / "run1" / "tasks"
           / "c00004_obs_convert_prepare-a128415ac1" / "attempt-001" / "stderr.log")
    log.parent.mkdir(parents=True)
    message = {
        "state": "error",
        "error": "Observation input belongs to a different cycle and no matching local file was found\n"
                 "  Requested cycle: 2026-01-31T00:00:00Z\n"
                 "  Configured input: /p/experiments/m3-7dias-20260130/science/runners/run_prepbufr.sh",
    }
    log.write_text(json.dumps(message))
    previous_bytes = dbpath.read_bytes()
    result = diagnose(tmp_path, query_pbs=False)
    assert result["status"] == "failure"
    assert result["diagnosis"]["code"] == "obs-cycle-path"
    assert result["workflow_failure"]["task"] == "c00004_obs_convert_prepare"
    assert "Requested cycle" in result["workflow_failure"]["error"]
    assert dbpath.read_bytes() == previous_bytes
