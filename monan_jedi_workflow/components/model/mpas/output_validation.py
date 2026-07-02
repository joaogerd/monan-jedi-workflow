"""MPAS forecast artifact and log validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ....core.validation import ValidationReport


@dataclass(frozen=True)
class MpasOutputContract:
    """Declare forecast products and log markers required for success.

    Parameters
    ----------
    required_files : tuple[Path, ...]
        Required non-empty files, relative to the run directory when not
        absolute.
    log_path : Path | None, default=None
        Optional model log path.
    required_log_markers : tuple[str, ...], default=()
        Markers that must appear in the model log.
    """

    required_files: tuple[Path, ...]
    log_path: Path | None = None
    required_log_markers: tuple[str, ...] = ()


def validate_output_contract(run_dir: Path, contract: MpasOutputContract) -> ValidationReport:
    """Validate output existence and optional model-log completion markers.

    Parameters
    ----------
    run_dir : Path
        Forecast run directory.
    contract : MpasOutputContract
        Required product and log contract.

    Returns
    -------
    ValidationReport
        All missing artifact and marker findings.
    """
    report = ValidationReport(subject=f"mpas_forecast:{run_dir}")
    for item in contract.required_files:
        path = item if item.is_absolute() else run_dir / item
        if not path.is_file() or path.stat().st_size == 0:
            report.add("mpas.output_missing", f"Required MPAS output is missing or empty: {path}", path=str(path))

    if contract.log_path is None:
        return report
    log_path = contract.log_path if contract.log_path.is_absolute() else run_dir / contract.log_path
    if not log_path.is_file():
        report.add("mpas.log_missing", f"Required MPAS log is missing: {log_path}", path=str(log_path))
        return report
    text = log_path.read_text(encoding="utf-8", errors="replace")
    for marker in contract.required_log_markers:
        if marker not in text:
            report.add("mpas.log_marker", f"MPAS log marker is missing: {marker}", path=str(log_path))
    return report
