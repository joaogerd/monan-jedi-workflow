"""Scheduler-independent execution backend contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


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
    """

    argv: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str] = field(default_factory=dict)
    stdout: Path | None = None
    stderr: Path | None = None

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
