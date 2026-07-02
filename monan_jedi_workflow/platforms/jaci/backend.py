"""Compose JACI scheduler, launcher, environment, and filesystem adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from ..base import ExecutionBackend, ExecutionHandle, ExecutionRequest
from ..jaci_backend import JaciPbsBackend
from ..jaci_pbs import JaciPbsResources, render_pbs
from .environment import JaciEnvironment
from .filesystem import JaciFilesystemPolicy
from .launcher import JaciMpiLauncher
from .scheduler import JaciSchedulerProfile


@dataclass(frozen=True)
class JaciExecutionPlan:
    """Resolved site execution plan written by a JACI dry-run."""

    script: Path
    request: ExecutionRequest
    resources: JaciPbsResources

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation of the resolved platform plan."""
        return {
            "script": str(self.script),
            "argv": list(self.request.argv),
            "cwd": str(self.request.cwd),
            "environment": dict(sorted(self.request.environment.items())),
            "pbs": {
                "queue": self.resources.queue,
                "walltime": self.resources.walltime,
                "select": self.resources.select,
                "ncpus": self.resources.ncpus,
                "mpiprocs": self.resources.mpiprocs,
                "job_name": self.resources.job_name,
                "memory_mb": self.resources.memory_mb,
            },
        }


class JaciPlatformBackend(ExecutionBackend):
    """Resolve and run a scientific request through the JACI platform policy."""

    def __init__(
        self,
        *,
        scheduler: JaciSchedulerProfile,
        launcher: JaciMpiLauncher,
        environment: JaciEnvironment,
        filesystem: JaciFilesystemPolicy,
        job_name: str,
        qsub: str = "qsub",
        qstat: str = "qstat",
        poll_seconds: int = 30,
        timeout_seconds: int | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.launcher = launcher
        self.environment = environment
        self.filesystem = filesystem
        self.job_name = job_name
        self.qsub = qsub
        self.qstat = qstat
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self._submitted: JaciPbsBackend | None = None

    def resolve(self, request: ExecutionRequest) -> JaciExecutionPlan:
        """Resolve one abstract request and render its PBS script without submit."""
        self.filesystem.validate(request.cwd)
        prepared = self.environment.apply(request)
        launched = replace(prepared, argv=(*self.launcher.render(prepared.resources), *prepared.argv))
        resources = self.scheduler.resolve(launched.resources, job_name=self.job_name)
        script = launched.cwd / ".monan-jedi-workflow" / "pbs" / f"{resources.job_name}.pbs"
        render_pbs(script, launched, resources, prelude=self.environment.prelude)
        return JaciExecutionPlan(script, launched, resources)

    def submit(self, request: ExecutionRequest) -> ExecutionHandle:
        """Render then submit one resolved JACI PBS job."""
        plan = self.resolve(request)
        backend = JaciPbsBackend(
            plan.resources,
            prelude=self.environment.prelude,
            qsub=self.qsub,
            qstat=self.qstat,
            poll_seconds=self.poll_seconds,
            timeout_seconds=self.timeout_seconds,
        )
        self._submitted = backend
        return backend.submit(plan.request)

    def wait(self, handle: ExecutionHandle) -> None:
        """Wait through the backend that submitted this stage's PBS job."""
        if self._submitted is None:
            raise RuntimeError("JACI wait requires a job submitted by this backend instance.")
        self._submitted.wait(handle)
