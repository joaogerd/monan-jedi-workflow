"""Portable provenance records for reproducible workflow runs."""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class RunProvenance:
    """Describe reproducibility metadata for one workflow run.

    Parameters
    ----------
    workflow : str
        Workflow identifier.
    case : str
        Case identifier.
    command : tuple[str, ...]
        Explicit command argument vector that started the run.
    code_revision : str | None
        Git commit or externally supplied source revision.
    resolved_config : Path
        Path to the resolved configuration saved in the workspace.
    created_at : str
        UTC creation time.
    environment : Mapping[str, str]
        Explicitly selected environment facts relevant to reproducibility.
    """

    workflow: str
    case: str
    command: tuple[str, ...]
    code_revision: str | None
    resolved_config: Path
    created_at: str = field(default_factory=_utc_now)
    environment: Mapping[str, str] = field(default_factory=dict)


def write_provenance(path: Path, provenance: RunProvenance) -> Path:
    """Write a stable JSON provenance record.

    Parameters
    ----------
    path : Path
        Destination JSON file.
    provenance : RunProvenance
        Reproducibility record to persist.

    Returns
    -------
    Path
        Written provenance path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(provenance)
    payload["resolved_config"] = str(provenance.resolved_config)
    payload["command"] = list(provenance.command)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def default_environment_facts() -> dict[str, str]:
    """Return portable runtime facts safe to include in provenance.

    Returns
    -------
    dict[str, str]
        Python and operating-system facts. Site-specific adapters may append
        module, scheduler, and compiler identifiers after explicit collection.
    """
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
    }
