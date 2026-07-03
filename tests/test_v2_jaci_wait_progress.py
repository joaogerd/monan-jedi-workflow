"""Tests for visible JACI PBS submission and wait progress."""

from __future__ import annotations

from collections import deque

from monan_jedi_workflow.platforms.base import ExecutionHandle
from monan_jedi_workflow.platforms.jaci_backend import JaciPbsBackend
from monan_jedi_workflow.platforms.jaci_pbs import JaciPbsResources


def test_jaci_wait_reports_state_transition_and_heartbeat(monkeypatch, capsys) -> None:
    """Foreground PBS waiting must remain visible while a job is queued or running."""
    backend = JaciPbsBackend(
        JaciPbsResources("pesqmini", "00:10:00", 1, 1, 1, "wps_ungrib_2026062000"),
        poll_seconds=1,
        progress_seconds=60,
    )
    states = deque(((True, "Q"), (True, "Q"), (True, "R"), (False, None)))
    moments = deque((0.0, 0.0, 0.0, 0.0, 61.0, 61.0, 61.0, 62.0))

    monkeypatch.setattr(backend, "_query", lambda _job_id: states.popleft())
    monkeypatch.setattr("monan_jedi_workflow.platforms.jaci_backend.time.monotonic", lambda: moments.popleft())
    monkeypatch.setattr("monan_jedi_workflow.platforms.jaci_backend.time.sleep", lambda _seconds: None)

    backend.wait(ExecutionHandle("287525.pbs-ha", "jaci-pbs"))

    output = capsys.readouterr().out
    assert "287525.pbs-ha state=Q; still waiting." in output
    assert "287525.pbs-ha still state=Q after 61s." in output
    assert "287525.pbs-ha state=R; still waiting." in output
    assert "287525.pbs-ha left qstat after 62s; scheduler wait completed." in output
