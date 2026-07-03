"""Artifact contracts and integrity records for V2 workflow stages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .validation import ValidationReport


class ArtifactFormat(str, Enum):
    """Supported high-level artifact formats."""

    TEXT = "text"
    JSON = "json"
    NETCDF = "netcdf"
    DIRECTORY = "directory"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ArtifactSpec:
    """Declare the contract of one stage input or output.

    Parameters
    ----------
    name : str
        Stable logical artifact name.
    relative_path : Path
        Path relative to the workflow workspace.
    producer : str
        Stage that creates the artifact, or ``external`` for supplied inputs.
    consumers : tuple[str, ...]
        Stages expected to consume the artifact.
    format : ArtifactFormat
        High-level physical format.
    required : bool, default=True
        Whether the artifact must exist for a successful producer stage.
    description : str, default=""
        English description of the artifact purpose.
    """

    name: str
    relative_path: Path
    producer: str
    consumers: tuple[str, ...]
    format: ArtifactFormat = ArtifactFormat.UNKNOWN
    required: bool = True
    description: str = ""

    def resolve(self, workspace: Path) -> Path:
        """Resolve the artifact path inside one workspace.

        Parameters
        ----------
        workspace : Path
            Root directory of the workflow run.

        Returns
        -------
        Path
            Absolute or normalized workspace-relative artifact path.
        """
        return workspace / self.relative_path


@dataclass(frozen=True)
class ArtifactRecord:
    """Record one observed artifact instance.

    Parameters
    ----------
    spec : ArtifactSpec
        Declared artifact contract.
    path : Path
        Observed artifact path.
    size_bytes : int
        Observed file size, or zero for a directory.
    sha256 : str | None
        SHA-256 digest for regular files.
    """

    spec: ArtifactSpec
    path: Path
    size_bytes: int
    sha256: str | None


def sha256_file(path: Path, *, block_size: int = 1024 * 1024) -> str:
    """Calculate a SHA-256 checksum for one regular file.

    Parameters
    ----------
    path : Path
        File to hash.
    block_size : int, default=1048576
        Number of bytes read per iteration.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def inspect_artifact(spec: ArtifactSpec, workspace: Path) -> tuple[ArtifactRecord | None, ValidationReport]:
    """Inspect one artifact against its existence and type contract.

    Parameters
    ----------
    spec : ArtifactSpec
        Artifact declaration to inspect.
    workspace : Path
        Workflow workspace containing the artifact.

    Returns
    -------
    tuple[ArtifactRecord | None, ValidationReport]
        Observed record when available and the complete validation report.
    """
    path = spec.resolve(workspace)
    report = ValidationReport(subject=f"artifact:{spec.name}")
    if not path.exists():
        if spec.required:
            report.add("artifact.missing", f"Required artifact is missing: {path}", path=str(path))
        return None, report

    if spec.format is ArtifactFormat.DIRECTORY and not path.is_dir():
        report.add("artifact.type", f"Artifact must be a directory: {path}", path=str(path))
        return None, report
    if spec.format is not ArtifactFormat.DIRECTORY and path.is_dir():
        report.add("artifact.type", f"Artifact must be a file: {path}", path=str(path))
        return None, report

    # Directories have no stable portable checksum. Their members are validated
    # by dedicated artifact contracts instead of inventing an implicit tree hash.
    checksum = None if path.is_dir() else sha256_file(path)
    size_bytes = 0 if path.is_dir() else path.stat().st_size
    return ArtifactRecord(spec, path, size_bytes, checksum), report
