"""Local process execution backend."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .base import ExecutionBackend, ExecutionHandle, ExecutionRequest


class LocalProcessBackend(ExecutionBackend):
    """Execute explicit requests as local child processes.

    This backend is intended for unit tests, smoke tests, and debugging. It
    uses the same request contract as scheduler adapters but does not treat a
    zero exit status as scientific validation.
    """

    def __init__(self) -> None:
        self._processes: dict[str, tuple[subprocess.Popen[str], object, object]] = {}
        self._counter = 0

    def submit(self, request: ExecutionRequest) -> ExecutionHandle:
        """Start a process and retain its log handles until completion."""
        request.cwd.mkdir(parents=True, exist_ok=True)
        stdout = request.stdout or request.cwd / "stdout.log"
        stderr = request.stderr or request.cwd / "stderr.log"
        stdout.parent.mkdir(parents=True, exist_ok=True)
        stderr.parent.mkdir(parents=True, exist_ok=True)
        out_handle = stdout.open("w", encoding="utf-8")
        err_handle = stderr.open("w", encoding="utf-8")
        environment = {**os.environ, **request.environment}
        process = subprocess.Popen(request.argv, cwd=request.cwd, env=environment, stdout=out_handle, stderr=err_handle, text=True)
        self._counter += 1
        identifier = f"local-{self._counter}"
        self._processes[identifier] = (process, out_handle, err_handle)
        return ExecutionHandle(identifier, "local")

    def wait(self, handle: ExecutionHandle) -> None:
        """Wait for one process and raise when it exits unsuccessfully."""
        if handle.backend != "local" or handle.identifier not in self._processes:
            raise ValueError(f"Unknown local execution handle: {handle.identifier}")
        process, out_handle, err_handle = self._processes.pop(handle.identifier)
        try:
            code = process.wait()
        finally:
            out_handle.close()
            err_handle.close()
        if code:
            raise RuntimeError(f"Local process {handle.identifier} failed with return code {code}.")
