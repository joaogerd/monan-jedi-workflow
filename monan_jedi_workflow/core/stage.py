"""Common lifecycle contract for executable scientific workflow stages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .validation import ValidationReport
from .workflow_spec import StageSpec


@dataclass(frozen=True)
class RunContext:
    """Runtime context supplied to every V2 stage.

    Parameters
    ----------
    workflow : str
        Name of the scientific workflow invoking the stage.
    case : str
        Stable case identifier.
    workspace : Path
        Root workspace for this workflow run.
    config : Mapping[str, object]
        Fully resolved configuration mapping.
    dry_run : bool, default=False
        Whether execution must plan without launching scientific software.
    """

    workflow: str
    case: str
    workspace: Path
    config: Mapping[str, object]
    dry_run: bool = False

    @property
    def state_path(self) -> Path:
        """Return the canonical persistent state path for this run."""
        return self.workspace / ".monan-jedi-workflow" / "run-state.json"


@dataclass(frozen=True)
class StageResult:
    """Summarize successful work performed by one stage.

    Parameters
    ----------
    message : str
        Human-readable English completion summary.
    artifacts : tuple[Path, ...], default=()
        Paths produced or published by the stage.
    """

    message: str
    artifacts: tuple[Path, ...] = ()


class Stage(ABC):
    """Base class for one reusable executable workflow stage.

    A stage owns a narrow scientific capability. It does not know whether it is
    invoked by a local runner, simpleWorkflow, ecFlow, or Cylc. Scheduler
    adapters may call the lifecycle methods individually; the local adapter
    uses the synchronous `submit` default.
    """

    @property
    @abstractmethod
    def spec(self) -> StageSpec:
        """Return the immutable declaration associated with this implementation."""

    def plan(self, context: RunContext) -> StageResult:
        """Describe intended work without modifying the workspace.

        Parameters
        ----------
        context : RunContext
            Resolved run context.

        Returns
        -------
        StageResult
            Human-readable plan summary.
        """
        return StageResult(message=f"Plan {self.spec.name}.")

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Validate inputs before preparation or submission.

        Parameters
        ----------
        context : RunContext
            Resolved run context.

        Returns
        -------
        ValidationReport
            Input-validation report. The default implementation is valid.
        """
        return ValidationReport(subject=f"stage:{self.spec.name}:inputs")

    def prepare(self, context: RunContext) -> StageResult:
        """Create deterministic workspace files required for execution.

        Parameters
        ----------
        context : RunContext
            Resolved run context.

        Returns
        -------
        StageResult
            Preparation summary.
        """
        return StageResult(message=f"Prepared {self.spec.name}.")

    def submit(self, context: RunContext) -> StageResult:
        """Submit or synchronously run the scientific stage.

        Parameters
        ----------
        context : RunContext
            Resolved run context.

        Returns
        -------
        StageResult
            Submission or execution summary.

        Notes
        -----
        Local stages may implement `run` only. Scheduler-backed stages should
        override this method and return after their scheduler submission.
        """
        return self.run(context)

    def wait(self, context: RunContext) -> StageResult:
        """Wait for a submitted external job when the stage requires it.

        Parameters
        ----------
        context : RunContext
            Resolved run context.

        Returns
        -------
        StageResult
            Completion summary. The default stage has no asynchronous job.
        """
        return StageResult(message=f"No wait required for {self.spec.name}.")

    @abstractmethod
    def run(self, context: RunContext) -> StageResult:
        """Perform synchronous scientific work for a local execution backend.

        Parameters
        ----------
        context : RunContext
            Resolved run context.

        Returns
        -------
        StageResult
            Execution summary and produced artifacts.
        """

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate outputs after successful execution.

        Parameters
        ----------
        context : RunContext
            Resolved run context.

        Returns
        -------
        ValidationReport
            Output-validation report. The default implementation is valid.
        """
        return ValidationReport(subject=f"stage:{self.spec.name}:outputs")

    def finalize(self, context: RunContext) -> StageResult:
        """Publish final metadata after output validation.

        Parameters
        ----------
        context : RunContext
            Resolved run context.

        Returns
        -------
        StageResult
            Finalization summary.
        """
        return StageResult(message=f"Finalized {self.spec.name}.")
