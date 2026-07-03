"""Tests for visible JACI PBS wait progress."""

from __future__ import annotations

from collections import deque

from monan_jedi_workflow.platforms.base import ExecutionHandle
from monan_jedi_workflow.platforms.jaci_backend import JaciPbsBackend
from monan_jedi_workflow.platforms.jaci_pbs import JaciPbsResources


def test_jaci_wait_reports_scheduler_states(monkeypatch, capsys) -> None:
    """Foreground waiting must show PBS status rather than remain silent."""
    backend = JaciPbsBackend(
        JaciPbsResources("pesqmini", "00:10:00", 1, 1, 1, "wps_ungrib_2026062000"),
        poll_seconds=1,
        progress_seconds=60,
    )
    states = deque(((True, "Q"), (True, "R"), (False, None)))
    monkeypatch.setattr(backend, "_query", lambda _job_id: states.popleft())
    monkeypatch.setattr("monan_jedi_workflow.platforms.jaci_backend.time.sleep", lambda _seconds: None)

    backend.wait(ExecutionHandle("287525.pbs-ha", "jaci-pbs"))

    output = capsys.readouterr().out
    assert "287525.pbs-ha state=Q; still waiting." in output
    assert "287525.pbs-ha state=R; still waiting." in output
    assert "287525.pbs-ha left qstat" in output
