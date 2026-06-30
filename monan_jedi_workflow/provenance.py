"""Small, dependency-free provenance helpers for resumable workflow stages."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest for a regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def stable_digest(value: Any) -> str:
    """Return a deterministic digest for a JSON-compatible value."""
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def file_record(path: Path, *, with_checksum: bool = False) -> dict[str, Any]:
    """Describe an existing regular file without depending on NetCDF tooling."""
    if not path.is_file():
        raise FileNotFoundError(f"Required file does not exist: {path}")
    record: dict[str, Any] = {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
    }
    if with_checksum:
        record["sha256"] = sha256_file(path)
    return record


def write_json_atomic(path: Path, value: dict[str, Any]) -> Path:
    """Write a JSON mapping atomically, preserving a prior valid product on error."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path
