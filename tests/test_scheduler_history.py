"""Regression tests for PBS jobs moving from active qstat to history."""

from __future__ import annotations

from collections import deque
from subprocess import CompletedProcess

import pytest

from monan_jedi_workflow.scheduler import PBSError, query


def _completed(argv: list[str], returncode: int, stdout: str = "", stderr: str = "") -> CompletedProcess[str]:
    return CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


def test_query_reads_finished_job_from_pbs_history(monkeypatch) -> None:
    """PBS exit code 35 at completion must fall back to qstat history."""
    responses = deque(
        [
            _completed(
                ["qstat", "-f", "363911.pbs-ha"],
                35,
                stderr=(
                    "qstat: 363911.pbs-ha Job has finished, use -x or -H "
                    "to obtain historical job information"
                ),
            ),
            _completed(
                ["qstat", "-x", "-f", "363911.pbs-ha"],
                0,
                stdout=(
                    "Job Id: 363911.pbs-ha\n"
                    "    Job_Name = jedi_2018041500\n"
                    "    job_state = F\n"
                    "    Exit_status = 0\n"
                ),
            ),
        ]
    )
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        return responses.popleft()

    monkeypatch.setattr("monan_jedi_workflow.scheduler.subprocess.run", fake_run)

    assert query("363911.pbs-ha") == (True, "F")
    assert commands == [
        ["qstat", "-f", "363911.pbs-ha"],
        ["qstat", "-x", "-f", "363911.pbs-ha"],
    ]


def test_query_preserves_real_qstat_failures(monkeypatch) -> None:
    """Scheduler/server failures must not be mistaken for normal completion."""
    monkeypatch.setattr(
        "monan_jedi_workflow.scheduler.subprocess.run",
        lambda command, **_kwargs: _completed(
            command,
            1,
            stderr="qstat: cannot connect to server pbs-ha",
        ),
    )

    with pytest.raises(PBSError, match="cannot connect to server"):
        query("363911.pbs-ha")
