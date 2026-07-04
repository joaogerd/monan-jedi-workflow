"""Scheduler-neutral execution backend contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ExecutionResources:
    """Describe abstract resources required by one scientific execution.

    Parameters
    ----------
    mpi_ranks : int, default=1
        Number of MPI ranks requested by the scientific stage.
    threads_per_rank : int, default=1
        OpenMP or equivalent threads assigned to each MPI rank.
    walltime : str | None, default=None
        Requested execution limit in ``HH:MM:SS`` form. Platform adapters may
        require it for scheduler submission.
    memory_mb : int | None, default=None
        Total requested memory in MiB. A platform may map this to its scheduler
        syntax or reject it when the site has no supported memory directive.
    """

    mpi_ranks: int = 1
    threads_per_rank: int = 1
    walltime: str | None = None
    memory_mb: int | None = None

    def __post_init__(self) -> None:
        """Reject invalid resource declarations before backend selection."""
        if not isinstance(self.mpi_ranks, int) or self.mpi_ranks < 1:
            raise ValueError("ExecutionResources.mpi_ranks must be a positive integer.")
        if not isinstance(self.threads_per_rank, int) or self.threads_per_rank < 1:
            raise ValueError("ExecutionResources.threads_per_rank must be a positive integer.")
        if self.memory_mb is not None and (not isinstance(self.memory_mb, int) or self.memory_mb < 1):
            raise ValueError("ExecutionResources.memory_mb must be a positive integer when set.")
        if self.walltime is not None:
            parts = self.walltime.split(":")
            if len(parts) != 3 or not all(part.isdigit() for part in parts):
                raise ValueError("ExecutionResources.walltime must use HH:MM:SS form when set.")
            hours, minutes, seconds = (int(part) for part in parts)
            if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
                raise ValueError("ExecutionResources.walltime has invalid clock fields.")

    @property
    def cpu_count(self) -> int:
        """Return the total requested CPUs before platform placement."""
        return self.mpi_ranks * self.threads_per_rank


@dataclass(frozen=True)
class ExecutionRequest:
    """Describe one explicit executable request.

    Parameters
    ----------
    argv : tuple[str, ...]
        Exact process argument vector. Shell command strings are intentionally
        excluded from this contract.
    cwd : Path
        Working directory used by the process.
    environment : Mapping[str, str], default={}
        Environment additions required by the executable.
    stdout : Path | None, default=None
        Optional stdout destination.
    stderr : Path | None, default=None
        Optional stderr destination.
    resources : ExecutionResources, default=ExecutionResources()
        Abstract scientific resource request resolved by a platform adapter.
    """

    argv: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str] = field(default_factory=dict)
    stdout: Path | None = None
    stderr: Path | None = None
    resources: ExecutionResources = field(default_factory=ExecutionResources)

    def __post_init__(self) -> None:
        """Reject empty argument vectors before dispatch."""
        if not self.argv or any(not item for item in self.argv):
            raise ValueError("ExecutionRequest.argv must contain non-empty arguments.")


@dataclass(frozen=True)
class ExecutionHandle:
    """Identify work submitted to an execution backend.

    Parameters
    ----------
    identifier : str
        Backend-specific process or scheduler identifier.
    backend : str
        Stable backend name such as ``local`` or ``jaci-pbs``.
    """

    identifier: str
    backend: str


class ExecutionBackend(ABC):
    """Submit and wait for explicit execution requests."""

    @abstractmethod
    def submit(self, request: ExecutionRequest) -> ExecutionHandle:
        """Submit a request and return the backend handle."""

    @abstractmethod
    def wait(self, handle: ExecutionHandle) -> None:
        """Wait for backend completion without declaring scientific success."""
