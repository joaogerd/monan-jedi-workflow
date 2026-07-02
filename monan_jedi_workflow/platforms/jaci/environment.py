"""Apply JACI environment policy to abstract execution requests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from string import Formatter
from typing import Mapping

from ..base import ExecutionRequest


@dataclass(frozen=True)\class JaciEnvironment:
    """Declare site prelude lines and environment values for JACI execution."""

    prelude: tuple[str, ...] = ()
    variables: Mapping[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """Validate platform environment keys and template fields."""
        values = {} if self.variables is None else dict(self.variables)
        if any(not isinstance(name, str) or not name or not isinstance(value, str) for name, value in values.items()):
            raise ValueError("JACI environment variables must map non-empty strings to strings.")
        allowed = {"mpi_ranks", "threads_per_rank"}
        fields = {field for value in values.values() for _, field, _, _ in Formatter().parse(value) if field}
        unknown = fields.difference(allowed)
        if unknown:
            raise ValueError(f"JACI environment uses unsupported field(s): {', '.join(sorted(unknown))}.")
        object.__setattr__(self, "variables", values)

    def apply(self, request: ExecutionRequest) -> ExecutionRequest:
        """Merge site environment and enforce the requested thread count."""
        values = {
            "mpi_ranks": request.resources.mpi_ranks,
            "threads_per_rank": request.resources.threads_per_rank,
        }
        environment = dict(request.environment)
        for name, template in self.variables.items():
            value = template.format_map(values)
            if name in environment and environment[name] != value:
                raise ValueError(f"JACI environment conflicts with scientific value for {name}.")
            environment[name] = value
        threads = str(request.resources.threads_per_rank)
        if "OMP_NUM_THREADS" in environment and environment["OMP_NUM_THREADS"] != threads:
            raise ValueError("OMP_NUM_THREADS must match resources.threads_per_rank on JACI.")
        environment["OMP_NUM_THREADS"] = threads
        return replace(request, environment=environment)
