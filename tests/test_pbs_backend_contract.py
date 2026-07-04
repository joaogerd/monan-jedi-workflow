"""PBS backend contract tests."""

from pathlib import Path

from monan_jedi_workflow.platforms.base import ExecutionRequest
from monan_jedi_workflow.platforms.jaci_backend import JaciPbsBackend
from monan_jedi_workflow.platforms.jaci_pbs import JaciPbsResources


def _program(path: Path, text: str) -> Path:
    """Write a small executable used to emulate one PBS command."""
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + text + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_jaci_backend_renders_submits_and_waits(tmp_path: Path) -> None:
    """JACI backend must render PBS and complete after a terminal qstat state."""
    qsub = _program(tmp_path / "qsub", "echo 12345.pbs-ha")
    qstat = _program(tmp_path / "qstat", "echo '    job_state = C'")
    request = ExecutionRequest(("/bin/true",), tmp_path / "run")
    backend = JaciPbsBackend(
        JaciPbsResources("pesqmidi", "00:30:00", 1, 128, 128, "mpas_test"),
        qsub=str(qsub),
        qstat=str(qstat),
        poll_seconds=1,
    )
    handle = backend.submit(request)
    backend.wait(handle)
    script = tmp_path / "run/.monan-jedi-workflow/pbs/mpas_test.pbs"
    assert handle.identifier == "12345.pbs-ha"
    assert script.is_file()
