"""Regression test for JACI qstat historical-completion diagnostics."""

from __future__ import annotations

from types import SimpleNamespace

from monan_jedi_workflow.platforms.jaci_backend import JaciPbsBackend
from monan_jedi_workflow.platforms.jaci_pbs import JaciPbsResources


def test_jaci_qstat_finished_job_is_a_terminal_wait_condition(monkeypatch) -> None:
    """JACI history guidance must not be surfaced as a watcher failure."""
    backend = JaciPbsBackend(
        JaciPbsResources("pesqmini", "00:10:00", 1, 1, 1, "mpas_init_2026062000"),
    )
    monkeypatch.setattr(
        "monan_jedi_workflow.platforms.jaci_backend.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="qstat: 287529.pbs-ha Job has finished, use -x or -H to obtain historical job information",
        ),
    )

    assert backend._query("287529.pbs-ha") == (False, None)
