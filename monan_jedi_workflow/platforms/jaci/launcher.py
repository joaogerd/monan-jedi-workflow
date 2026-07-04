"""Render JACI MPI launcher arguments from abstract resource requests."""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter

from ..base import ExecutionResources


@dataclass(frozen=True)
class JaciMpiLauncher:
    """Render a site-owned MPI launcher command prefix.

    The template may use only `mpi_ranks` and `threads_per_rank`; scientific
    component YAML never needs to name the launcher executable or syntax.
    """

    argv_template: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject empty commands and unsupported template placeholders."""
        if not self.argv_template or any(not item for item in self.argv_template):
            raise ValueError("JACI MPI launcher argv must contain non-empty strings.")
        allowed = {"mpi_ranks", "threads_per_rank"}
        fields = {name for item in self.argv_template for _, name, _, _ in Formatter().parse(item) if name}
        unknown = fields.difference(allowed)
        if unknown:
            raise ValueError(f"JACI MPI launcher uses unsupported field(s): {', '.join(sorted(unknown))}.")

    def render(self, resources: ExecutionResources) -> tuple[str, ...]:
        """Render the launcher prefix for one concrete resource request."""
        values = {
            "mpi_ranks": resources.mpi_ranks,
            "threads_per_rank": resources.threads_per_rank,
        }
        return tuple(item.format_map(values) for item in self.argv_template)
