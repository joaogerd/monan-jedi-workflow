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
    stage validates its declared outputs after ``wait`` returns. Submission and
    periodic scheduler-status messages are deliberately emitted to stdout so a
    foreground ``stage run`` does not appear stalled while PBS queues or runs a
    job.
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
        progress_seconds: int = 60,
    ) -> None:
        if poll_seconds < 1:
            raise ValueError("poll_seconds must be at least 1.")
        if progress_seconds < 1:
            raise ValueError("progress_seconds must be at least 1.")
        self.resources, self.prelude = resources, prelude
        self.qsub, self.qstat = qsub, qstat
        self.poll_seconds, self.timeout_seconds = poll_seconds, timeout_seconds
        self.progress_seconds = progress_seconds

    def submit(self, request: ExecutionRequest) -> ExecutionHandle:
        """Render one PBS file, submit it, report the job id, and return it."""
        script = request.cwd / ".monan-jedi-workflow" / "pbs" / f"{self.resources.job_name}.pbs"
        render_pbs(script, request, self.resources, prelude=self.prelude)
        result = subprocess.run((self.qsub, str(script)), cwd=request.cwd, text=True, capture_output=True, check=False)
        if result.returncode:
            raise JaciPbsError(f"qsub failed with return code {result.returncode}: {result.stderr.strip()}")
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise JaciPbsError("qsub returned no PBS job identifier.")
        handle = ExecutionHandle(lines[-1].split()[0], "jaci-pbs")
        print(
            f"[JACI PBS] submitted {handle.identifier} ({self.resources.job_name}); "
            "waiting for scheduler completion.",
            flush=True,
        )
        return handle

    def _query(self, job_id: str) -> tuple[bool, str | None]:
        """Return JACI job visibility and state from ``qstat -f``."""
        result = subprocess.run((self.qstat, "-f", job_id), text=True, capture_output=True, check=False)
        text = "\n".join(item for item in (result.stdout.strip(), result.stderr.strip()) if item)
        if result.returncode:
            if any(marker in text.lower() for marker in _NOT_FOUND):
                return False, None
            raise JaciPbsError(f"qstat failed for {job_id}: {text}")
        match = _STATE.search(result.stdout)
        return True, match.group(1).upper() if match else None

    def wait(self, handle: ExecutionHandle) -> None:
        """Wait with state changes and periodic heartbeat messages.

        The method does not infer scientific success from PBS state. It reports
        scheduler visibility only, then returns so the stage output contract can
        decide whether the scientific executable actually succeeded.
        """
        if handle.backend != "jaci-pbs":
            raise ValueError(f"Unexpected backend handle: {handle.backend}")
        started = time.monotonic()
        last_state: str | None = None
        last_progress = started
        while True:
            visible, state = self._query(handle.identifier)
            elapsed = int(time.monotonic() - started)
            if not visible or state in {"C", "F"}:
                suffix = f"state={state}" if state is not None else "left qstat"
                print(
                    f"[JACI PBS] {handle.identifier} {suffix} after {elapsed}s; "
                    "scheduler wait completed.",
                    flush=True,
                )
                return
            if state != last_state:
                printable_state = state or "unknown"
                print(
                    f"[JACI PBS] {handle.identifier} state={printable_state}; still waiting.",
                    flush=True,
                )
                last_state = state
                last_progress = time.monotonic()
            elif time.monotonic() - last_progress >= self.progress_seconds:
                printable_state = state or "unknown"
                print(
                    f"[JACI PBS] {handle.identifier} still state={printable_state} after {elapsed}s.",
                    flush=True,
                )
                last_progress = time.monotonic()
            if self.timeout_seconds is not None and time.monotonic() - started >= self.timeout_seconds:
                raise TimeoutError(f"Timed out waiting for JACI PBS job {handle.identifier}.")
            time.sleep(self.poll_seconds)
