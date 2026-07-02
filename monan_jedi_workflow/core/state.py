"""Persistent state for restart-safe V2 stage execution."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class StageStatus(str, Enum):
    """Lifecycle state of one stage attempt."""

    PLANNED = "planned"
    PREPARED = "prepared"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


_ALLOWED_TRANSITIONS: dict[StageStatus, frozenset[StageStatus]] = {
    StageStatus.PLANNED: frozenset({StageStatus.PREPARED, StageStatus.SKIPPED, StageStatus.FAILED}),
    StageStatus.PREPARED: frozenset({StageStatus.RUNNING, StageStatus.SKIPPED, StageStatus.FAILED}),
    StageStatus.RUNNING: frozenset({StageStatus.SUCCEEDED, StageStatus.FAILED}),
    # A successful stage may be explicitly invalidated when its declared output
    # disappears or no longer satisfies the current artifact contract.
    StageStatus.SUCCEEDED: frozenset({StageStatus.PLANNED}),
    StageStatus.FAILED: frozenset({StageStatus.PLANNED, StageStatus.PREPARED}),
    StageStatus.SKIPPED: frozenset({StageStatus.PLANNED, StageStatus.PREPARED}),
}


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class StageState:
    """Persisted state for one named workflow stage.

    Parameters
    ----------
    name : str
        Stable stage identifier.
    status : StageStatus, default=StageStatus.PLANNED
        Current lifecycle state.
    updated_at : str, default=""
        UTC timestamp of the latest state transition.
    message : str, default=""
        Human-readable explanation of the latest transition.
    """

    name: str
    status: StageStatus = StageStatus.PLANNED
    updated_at: str = ""
    message: str = ""

    def transition(self, target: StageStatus, *, message: str = "") -> None:
        """Move the stage to an allowed lifecycle state.

        Parameters
        ----------
        target : StageStatus
            Requested next lifecycle state.
        message : str, default=""
            Human-readable reason or execution summary.

        Raises
        ------
        ValueError
            Raised when the requested transition is not allowed.
        """
        if target is self.status:
            self.updated_at = utc_now()
            self.message = message
            return
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"Invalid stage transition: {self.status.value} -> {target.value}.")
        self.status = target
        self.updated_at = utc_now()
        self.message = message


@dataclass
class RunState:
    """Persist and restore state for one workflow run.

    Parameters
    ----------
    workflow : str
        Workflow identifier.
    case : str
        Case identifier.
    stages : dict[str, StageState], default={}
        State records keyed by stage name.
    """

    workflow: str
    case: str
    stages: dict[str, StageState] = field(default_factory=dict)

    def stage(self, name: str) -> StageState:
        """Return the persisted state for one stage, creating it when absent."""
        return self.stages.setdefault(name, StageState(name=name, updated_at=utc_now()))

    def save(self, path: Path) -> None:
        """Atomically write state to JSON.

        Parameters
        ----------
        path : Path
            Destination state-file path.

        Notes
        -----
        The temporary file is placed beside the destination so replacement is
        atomic on the same filesystem. This prevents a partial JSON file after
        a process interruption.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "workflow": self.workflow,
            "case": self.case,
            "stages": {name: asdict(state) | {"status": state.status.value} for name, state in self.stages.items()},
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    @classmethod
    def load(cls, path: Path, *, workflow: str, case: str) -> "RunState":
        """Load existing state or create a new state record.

        Parameters
        ----------
        path : Path
            State-file path.
        workflow : str
            Expected workflow identifier.
        case : str
            Expected case identifier.

        Returns
        -------
        RunState
            Existing compatible state or a new empty state.

        Raises
        ------
        ValueError
            Raised when an existing state belongs to another workflow or case.
        """
        if not path.exists():
            return cls(workflow=workflow, case=case)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("workflow") != workflow or payload.get("case") != case:
            raise ValueError(f"State file {path} belongs to another workflow or case.")
        stages = {
            name: StageState(
                name=item["name"],
                status=StageStatus(item["status"]),
                updated_at=item.get("updated_at", ""),
                message=item.get("message", ""),
            )
            for name, item in payload.get("stages", {}).items()
        }
        return cls(workflow=workflow, case=case, stages=stages)
