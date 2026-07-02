"""JACI PBS execution backend."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from .base import ExecutionBackend, ExecutionHandle, ExecutionRequest
from .jaci_pbs import JaciPbsResources, render_pbs

_NOT_FOUND = ("unknown job id", "unknown job", "not found", "does not exist")
_STATE = re.compile(r"^\s*job_state\s*=\s*([A-Za-z])\s*$", re.MULTILINE)


class JaciPbsError(RuntimeError):
    """Raised when a JACI PBS submission or status query fails."""


class JaciPbsBackend(ExecutionBackend):
    """Submit explicit requests to JACI PBS and wait for scheduler completion.

    Scheduler completion remains distinct from scientific success. The calling
    stage must validate its declared outputs after `wait` returns.
    """

    def __init__(
        self,
        resources: JaciPbsResources,
        *,
        prelude: tuple[str, ...] = (),
        qsub: str = "qsub",
        qstat: str = "qstat",
        poll_seconds: int = 30,
        timeout_seconds: int | None = None,
    ) -> None:
        if poll_seconds < 1:
            raise ValueError("poll_seconds must be at least 1.")
        self.resources, self.prelude = resources, prelude
        self.qsub, self.qstat = qsub, qstat
        self.poll_seconds, self.timeout_seconds = poll_seconds, timeout_seconds

    def submit(self, request: ExecutionRequest) -> ExecutionHandle:
        """Render one PBS file, submit it, and return the JACI job identifier."""
        script = request.cwd / ".monan-jedi-workflow" / "pbs" / f"{self.resources.job_name}.pbs"
        render_pbs(script, request, self.resources, prelude=self.prelude)
        result = subprocess.run((self.qsub, str(script)), cwd=request.cwd, text=True, capture_output=True, check=False)
        if result.returncode:
            raise JaciPbsError(f"qsub failed with return code {result.returncode}: {result.stderr.strip()}")
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise JaciPbsError("qsub returned no PBS job identifier.")
        return ExecutionHandle(lines[-1].split()[0], "jaci-pbs")

    def _query(self, job_id: str) -> tuple[bool, str | None]:
        """Return JACI job visibility and state from `qstat -f`."""
        result = subprocess.run((self.qstat, "-f", job_id), text=True, capture_output=True, check=False)
        text = "\n".join(item for item in (result.stdout.strip(), result.stderr.strip()) if item)
        if result.returncode:
            if any(marker in text.lower() for marker in _NOT_FOUND):
                return False, None
            raise JaciPbsError(f"qstat failed for {job_id}: {text}")
        match = _STATE.search(result.stdout)
        return True, match.group(1).upper() if match else None

    def wait(self, handle: ExecutionHandle) -> None:
        """Wait until JACI no longer reports a running or queued job."""
        if handle.backend != "jaci-pbs":
            raise ValueError(f"Unexpected backend handle: {handle.backend}")
        started, last = time.monotonic(), None
        while True:
            visible, state = self._query(handle.identifier)
            if not visible or state in {"C", "F"}:
                return
            if self.timeout_seconds is not None and time.monotonic() - started >= self.timeout_seconds:
                raise TimeoutError(f"Timed out waiting for JACI PBS job {handle.identifier}.")
            last = state or last
            time.sleep(self.poll_seconds)
