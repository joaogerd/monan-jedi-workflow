"""Translate abstract execution resources into JACI PBS placement."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from ..base import ExecutionResources
from ..jaci_pbs import JaciPbsResources


@dataclass(frozen=True)
class JaciSchedulerProfile:
    """Describe JACI node capacity and queue routing for one stage category.

    Parameters
    ----------
    queue : str
        Site queue selected for this operational stage category.
    cores_per_node : int
        CPUs available in one requested PBS chunk.
    max_mpi_ranks_per_node : int
        Maximum MPI ranks allowed in one requested PBS chunk.
    """

    queue: str
    cores_per_node: int
    max_mpi_ranks_per_node: int

    def __post_init__(self) -> None:
        """Reject impossible site capacity declarations."""
        if not self.queue:
            raise ValueError("JACI scheduler queue must be non-empty.")
        if self.cores_per_node < 1 or self.max_mpi_ranks_per_node < 1:
            raise ValueError("JACI node capacities must be positive integers.")

    def resolve(self, request: ExecutionResources, *, job_name: str) -> JaciPbsResources:
        """Resolve one abstract request into PBS chunks and ranks.

        The scheduler may allocate a small number of spare ranks when the total
        rank count cannot be divided evenly across chunks. The MPI launcher still
        starts exactly `request.mpi_ranks` processes.
        """
        if request.walltime is None:
            raise ValueError("JACI execution requires resources.walltime.")
        select = ceil(request.mpi_ranks / self.max_mpi_ranks_per_node)
        mpiprocs = ceil(request.mpi_ranks / select)
        ncpus = mpiprocs * request.threads_per_rank
        if ncpus > self.cores_per_node:
            raise ValueError(
                f"JACI request needs {ncpus} CPUs per chunk but the profile allows {self.cores_per_node}."
            )
        return JaciPbsResources(
            queue=self.queue,
            walltime=request.walltime,
            select=select,
            ncpus=ncpus,
            mpiprocs=mpiprocs,
            job_name=job_name,
            memory_mb=ceil(request.memory_mb / select) if request.memory_mb is not None else None,
        )
