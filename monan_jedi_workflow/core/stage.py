"""Common lifecycle contract for executable scientific workflow stages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
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
        Whether execution must plan without modifying stage run directories.
    prepare_only : bool, default=False
        Whether the workflow must validate static inputs, stage links, and render
        templates without submitting or running scientific software. Declared
        upstream artifacts may be represented by dangling links in this mode.
    """

    workflow: str
    case: str
    workspace: Path
    config: Mapping[str, object]
    dry_run: bool = False
    prepare_only: bool = False

    def __post_init__(self) -> None:
        """Reject mutually exclusive pre-execution modes."""
        if self.dry_run and self.prepare_only:
            raise ValueError("RunContext dry_run and prepare_only are mutually exclusive.")

    @property
    def state_path(self) -> Path:
        """Return the canonical persistent state path for this run."""
        return self.workspace / ".monan-jedi-workflow" / "run-state.json"


@dataclass(frozen=True)
class StageResult:
    """Summarize successful work performed by one stage."""

    message: str
    artifacts: tuple[Path, ...] = ()


class Stage(ABC):
    """Base class for one reusable executable workflow stage."""

    @property
    @abstractmethod
    def spec(self) -> StageSpec:
        """Return the immutable declaration associated with this implementation."""

    def plan(self, context: RunContext) -> StageResult:
        """Describe intended work without modifying the workspace."""
        return StageResult(message=f"Plan {self.spec.name}.")

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Validate all scientific inputs required before stage submission."""
        return ValidationReport(subject=f"stage:{self.spec.name}:inputs")

    def validate_preparation_inputs(self, context: RunContext) -> ValidationReport:
        """Validate inputs required for safe workspace materialization.

        The default matches full scientific input validation. Stages whose
        inputs are outputs of downstream campaign work may override this hook to
        validate configuration only during a preparation-only preflight.
        """
        return self.validate_inputs(context)

    def prepare(self, context: RunContext) -> StageResult:
        """Create deterministic workspace files required for execution."""
        return StageResult(message=f"Prepared {self.spec.name}.")

    def submit(self, context: RunContext) -> StageResult:
        """Submit or synchronously run the scientific stage."""
        return self.run(context)

    def wait(self, context: RunContext) -> StageResult:
        """Wait for a submitted external job when the stage requires it."""
        return StageResult(message=f"No wait required for {self.spec.name}.")

    @abstractmethod
    def run(self, context: RunContext) -> StageResult:
        """Perform synchronous scientific work for a local execution backend."""

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate outputs after successful execution."""
        return ValidationReport(subject=f"stage:{self.spec.name}:outputs")

    def finalize(self, context: RunContext) -> StageResult:
        """Publish final metadata after output validation."""
        return StageResult(message=f"Finalized {self.spec.name}.")
