"""JACI PBS job rendering from explicit execution requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from .base import ExecutionRequest


@dataclass(frozen=True)
class JaciPbsResources:
    """PBS resources for one JACI job.

    Parameters
    ----------
    queue : str
        PBS queue name.
    walltime : str
        PBS walltime in ``HH:MM:SS`` form.
    select : int
        Number of selected chunks.
    ncpus : int
        CPUs per selected chunk.
    mpiprocs : int
        MPI ranks per selected chunk.
    job_name : str
        Scheduler-visible job name.
    """

    queue: str
    walltime: str
    select: int
    ncpus: int
    mpiprocs: int
    job_name: str

    def __post_init__(self) -> None:
        """Reject invalid resource values before script rendering."""
        if not self.queue or not self.walltime or not self.job_name:
            raise ValueError("JACI PBS queue, walltime, and job_name must be non-empty.")
        if min(self.select, self.ncpus, self.mpiprocs) < 1:
            raise ValueError("JACI PBS select, ncpus, and mpiprocs must be positive.")


def render_pbs(
    path: Path,
    request: ExecutionRequest,
    resources: JaciPbsResources,
    *,
    prelude: tuple[str, ...] = (),
) -> Path:
    """Render one executable PBS script.

    Parameters
    ----------
    path : Path
        Destination script path.
    request : ExecutionRequest
        Explicit program and runtime contract.
    resources : JaciPbsResources
        Queue and resource declaration.
    prelude : tuple[str, ...], default=()
        Site-managed shell lines, such as module loads. They are explicit
        configuration, not hidden workflow behavior.

    Returns
    -------
    Path
        Written executable PBS script.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    exports = [f"export {name}={shlex.quote(value)}" for name, value in sorted(request.environment.items())]
    stdout = request.stdout or request.cwd / "stdout.log"
    stderr = request.stderr or request.cwd / "stderr.log"
    command = shlex.join(request.argv)
    lines = (
        "#!/usr/bin/env bash",
        f"#PBS -N {resources.job_name}",
        f"#PBS -q {resources.queue}",
        f"#PBS -l select={resources.select}:ncpus={resources.ncpus}:mpiprocs={resources.mpiprocs}",
        f"#PBS -l walltime={resources.walltime}",
        "#PBS -j oe",
        "",
        "set -euo pipefail",
        f"cd {shlex.quote(str(request.cwd))}",
        *prelude,
        *exports,
        "ulimit -s unlimited || true",
        f"{command} > {shlex.quote(str(stdout))} 2> {shlex.quote(str(stderr))}",
        "",
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(0o755)
    return path
