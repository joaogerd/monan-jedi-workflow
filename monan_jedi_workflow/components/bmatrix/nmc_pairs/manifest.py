"""BFLOW hand-off manifest serialization for validated NMC pairs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .model import NmcPairError, normalize_time


_MANIFEST_COLUMNS = ("valid_time", "f048", "f024")


@dataclass(frozen=True)
class BflowManifestEntry:
    """Describe one BFLOW state-file pair.

    Parameters
    ----------
    valid_time : str
        Shared valid time for both state files.
    f048 : Path
        Earlier forecast state file with the longer lead time.
    f024 : Path
        Later forecast state file with the shorter lead time.
    """

    valid_time: str
    f048: Path
    f024: Path

    def __post_init__(self) -> None:
        """Normalize the public timestamp representation."""
        object.__setattr__(self, "valid_time", normalize_time(self.valid_time))


@dataclass(frozen=True)
class BflowManifest:
    """Represent the stable hand-off contract between NMC pairs and BFLOW.

    Parameters
    ----------
    entries : tuple[BflowManifestEntry, ...]
        Ordered state-file pairs.
    """

    entries: tuple[BflowManifestEntry, ...]

    def __post_init__(self) -> None:
        """Require a strictly ordered manifest without duplicate valid times."""
        times = tuple(entry.valid_time for entry in self.entries)
        if len(set(times)) != len(times):
            raise NmcPairError("BFLOW manifest valid times must be unique.")
        if times != tuple(sorted(times)):
            raise NmcPairError("BFLOW manifest entries must be ordered by valid_time.")


def write_bflow_manifest(path: Path, manifest: BflowManifest) -> Path:
    """Write a BFLOW manifest atomically.

    Parameters
    ----------
    path : Path
        Destination TSV path.
    manifest : BflowManifest
        Ordered manifest to persist.

    Returns
    -------
    Path
        Written TSV path.

    Notes
    -----
    The column names and order are the public contract for BFLOW. They are not
    tied to a repository name, branch name, or implementation language.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=_MANIFEST_COLUMNS, delimiter="\t")
        writer.writeheader()
        for entry in manifest.entries:
            writer.writerow(
                {
                    "valid_time": entry.valid_time,
                    "f048": str(entry.f048),
                    "f024": str(entry.f024),
                }
            )
    temporary.replace(path)
    return path


def read_bflow_manifest(path: Path) -> BflowManifest:
    """Read and validate a BFLOW TSV manifest.

    Parameters
    ----------
    path : Path
        Manifest TSV path.

    Returns
    -------
    BflowManifest
        Parsed, normalized, and ordered manifest.

    Raises
    ------
    NmcPairError
        Raised when required columns are missing or an entry is incomplete.
    """
    if not path.is_file():
        raise NmcPairError(f"BFLOW manifest is missing: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if tuple(reader.fieldnames or ()) != _MANIFEST_COLUMNS:
            raise NmcPairError(
                f"BFLOW manifest columns must be {_MANIFEST_COLUMNS}; received {tuple(reader.fieldnames or ())}."
            )
        entries: list[BflowManifestEntry] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                valid_time = row["valid_time"]
                f048 = row["f048"]
                f024 = row["f024"]
            except KeyError as exc:
                raise NmcPairError(f"Incomplete BFLOW manifest row {row_number}.") from exc
            if not valid_time or not f048 or not f024:
                raise NmcPairError(f"Incomplete BFLOW manifest row {row_number}.")
            entries.append(BflowManifestEntry(valid_time, Path(f048), Path(f024)))
    return BflowManifest(tuple(entries))
