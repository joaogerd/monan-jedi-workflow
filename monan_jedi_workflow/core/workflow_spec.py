"""Scheduler-independent workflow specifications.

A workflow specification records scientific task dependencies without encoding
PBS, simpleWorkflow, ecFlow, Cylc, or local-runner details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


class WorkflowSpecificationError(ValueError):
    """Raised when a workflow specification is structurally invalid."""


@dataclass(frozen=True)
class StageSpec:
    """Describe one named stage in a workflow dependency graph.

    Parameters
    ----------
    name : str
        Stable stage identifier within the workflow.
    command : str
        Public CLI command or registered stage entry point used by adapters.
    needs : tuple[str, ...], default=()
        Names of stages that must succeed before this stage is eligible.
    description : str, default=""
        Concise English explanation of the scientific or operational purpose.

    Notes
    -----
    `StageSpec` intentionally contains no scheduler resources. Queue, walltime,
    and placement are platform concerns; scientific dependencies are not.
    """

    name: str
    command: str
    needs: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        """Validate the stage declaration."""
        if not self.name or self.name.strip() != self.name:
            raise WorkflowSpecificationError("Stage names must be non-empty and trimmed.")
        if not self.command or self.command.strip() != self.command:
            raise WorkflowSpecificationError("Stage commands must be non-empty and trimmed.")
        if len(set(self.needs)) != len(self.needs):
            raise WorkflowSpecificationError(f"Stage '{self.name}' declares duplicate dependencies.")
        if self.name in self.needs:
            raise WorkflowSpecificationError(f"Stage '{self.name}' cannot depend on itself.")


@dataclass(frozen=True)
class WorkflowSpec:
    """Describe a complete scheduler-neutral scientific workflow.

    Parameters
    ----------
    name : str
        Stable workflow identifier, such as ``bmatrix`` or ``das_cycle``.
    stages : tuple[StageSpec, ...]
        All stages belonging to the workflow.
    description : str, default=""
        Concise English description of the workflow objective.

    Raises
    ------
    WorkflowSpecificationError
        Raised when stage names are duplicated, dependencies are missing, or the
        graph contains a dependency cycle.
    """

    name: str
    stages: tuple[StageSpec, ...] = field(default_factory=tuple)
    description: str = ""

    def __post_init__(self) -> None:
        """Validate names, dependency references, and graph acyclicity."""
        if not self.name or self.name.strip() != self.name:
            raise WorkflowSpecificationError("Workflow names must be non-empty and trimmed.")
        names = [stage.name for stage in self.stages]
        if len(set(names)) != len(names):
            raise WorkflowSpecificationError(f"Workflow '{self.name}' has duplicate stage names.")

        declared = set(names)
        for stage in self.stages:
            missing = set(stage.needs).difference(declared)
            if missing:
                values = ", ".join(sorted(missing))
                raise WorkflowSpecificationError(
                    f"Stage '{stage.name}' depends on undefined stage(s): {values}."
                )

        # Resolving the order during construction detects cycles before an adapter
        # renders a workflow definition that no scheduler could execute correctly.
        self.topological_order()

    @classmethod
    def from_stages(
        cls,
        name: str,
        stages: Iterable[StageSpec],
        *,
        description: str = "",
    ) -> "WorkflowSpec":
        """Build a specification from any iterable of stage declarations.

        Parameters
        ----------
        name : str
            Stable workflow identifier.
        stages : Iterable[StageSpec]
            Stage declarations to freeze into the specification.
        description : str, default=""
            Concise workflow description.

        Returns
        -------
        WorkflowSpec
            Validated immutable workflow specification.
        """
        return cls(name=name, stages=tuple(stages), description=description)

    def stage(self, name: str) -> StageSpec:
        """Return one stage by name.

        Parameters
        ----------
        name : str
            Stage identifier.

        Returns
        -------
        StageSpec
            The matching stage declaration.

        Raises
        ------
        WorkflowSpecificationError
            Raised when no stage uses the requested identifier.
        """
        for stage in self.stages:
            if stage.name == name:
                return stage
        raise WorkflowSpecificationError(f"Workflow '{self.name}' has no stage named '{name}'.")

    def topological_order(self) -> tuple[str, ...]:
        """Return a deterministic dependency-respecting stage order.

        Returns
        -------
        tuple[str, ...]
            Stage names ordered so that each dependency precedes its consumer.

        Raises
        ------
        WorkflowSpecificationError
            Raised when the dependency graph contains a cycle.
        """
        pending = {stage.name: set(stage.needs) for stage in self.stages}
        order: list[str] = []

        while pending:
            ready = sorted(name for name, needs in pending.items() if not needs)
            if not ready:
                participants = ", ".join(sorted(pending))
                raise WorkflowSpecificationError(
                    f"Workflow '{self.name}' contains a dependency cycle involving: {participants}."
                )
            order.extend(ready)
            for name in ready:
                pending.pop(name)
            for needs in pending.values():
                needs.difference_update(ready)

        return tuple(order)
