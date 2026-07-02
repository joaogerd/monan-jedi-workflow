"""Validate JACI workspaces against optional site filesystem policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JaciFilesystemPolicy:
    """Restrict execution workspaces to declared JACI filesystem roots.

    An empty root set intentionally permits any absolute workspace and is useful
    for local development or a first site-profile bootstrap.
    """

    allowed_workspace_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        """Require absolute roots so path-policy checks are deterministic."""
        if any(not root.is_absolute() for root in self.allowed_workspace_roots):
            raise ValueError("JACI allowed workspace roots must be absolute paths.")

    def validate(self, workspace: Path) -> None:
        """Raise when an explicitly restricted workspace is outside all roots."""
        resolved = workspace.resolve()
        if not self.allowed_workspace_roots:
            return
        if not any(resolved.is_relative_to(root.resolve()) for root in self.allowed_workspace_roots):
            roots = ", ".join(str(root) for root in self.allowed_workspace_roots)
            raise ValueError(f"JACI workspace {resolved} is outside allowed roots: {roots}.")
