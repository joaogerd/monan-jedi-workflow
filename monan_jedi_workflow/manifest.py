"""Stage manifest helpers for cyclic MONAN-JEDI workflows.

Manifests capture provenance for one stage attempt. They are data records only:
creating them does not execute stages, submit jobs, create scientific products or
inspect remote systems.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

VALID_STATUSES = frozenset({"planned", "running", "success", "failed"})


def utc_now_iso() -> str:
    """Return a UTC timestamp suitable for manifest records."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_config_hash(configuration: dict[str, Any]) -> str:
    """Hash a configuration mapping through deterministic YAML serialization."""
    payload = yaml.safe_dump(configuration, sort_keys=True, allow_unicode=True)
    return sha256(payload.encode("utf-8")).hexdigest()


def file_fingerprint(path: Path) -> dict[str, Any]:
    """Return a lightweight fingerprint for an existing regular file."""
    stat = path.stat()
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


@dataclass(frozen=True)
class StageManifest:
    """Provenance record for one stage attempt."""

    experiment: str
    cycle_id: str
    stage: str
    attempt: int
    status: str
    created_at: str
    updated_at: str
    config_hash: str
    argv: tuple[str, ...] = ()
    executor: str = "local"
    scheduler_job_id: str | None = None
    inputs: tuple[dict[str, Any], ...] = ()
    outputs: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid stage manifest status: {self.status}")
        if self.attempt < 1:
            raise ValueError("Manifest attempt must be >= 1")

    def to_mapping(self) -> dict[str, Any]:
        """Return a YAML-serializable representation."""
        data = asdict(self)
        data["argv"] = list(self.argv)
        data["inputs"] = list(self.inputs)
        data["outputs"] = list(self.outputs)
        return data

    def with_status(
        self,
        status: str,
        *,
        scheduler_job_id: str | None = None,
        outputs: tuple[dict[str, Any], ...] | None = None,
    ) -> "StageManifest":
        """Return a new manifest with updated runtime status."""
        return StageManifest(
            experiment=self.experiment,
            cycle_id=self.cycle_id,
            stage=self.stage,
            attempt=self.attempt,
            status=status,
            created_at=self.created_at,
            updated_at=utc_now_iso(),
            config_hash=self.config_hash,
            argv=self.argv,
            executor=self.executor,
            scheduler_job_id=scheduler_job_id if scheduler_job_id is not None else self.scheduler_job_id,
            inputs=self.inputs,
            outputs=self.outputs if outputs is None else outputs,
            metadata=dict(self.metadata),
        )


def create_stage_manifest(
    *,
    experiment: str,
    cycle_id: str,
    stage: str,
    attempt: int,
    resolved_config: dict[str, Any],
    argv: list[str] | tuple[str, ...] = (),
    executor: str = "local",
    inputs: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    metadata: dict[str, Any] | None = None,
) -> StageManifest:
    """Create an initial planned manifest for a stage attempt."""
    now = utc_now_iso()
    return StageManifest(
        experiment=experiment,
        cycle_id=cycle_id,
        stage=stage,
        attempt=attempt,
        status="planned",
        created_at=now,
        updated_at=now,
        config_hash=stable_config_hash(resolved_config),
        argv=tuple(argv),
        executor=executor,
        inputs=tuple(inputs),
        metadata={} if metadata is None else dict(metadata),
    )


def write_manifest(path: Path, manifest: StageManifest) -> None:
    """Write a manifest atomically using a temporary sibling file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(manifest.to_mapping(), stream, sort_keys=False, allow_unicode=True)
    temporary.replace(path)
