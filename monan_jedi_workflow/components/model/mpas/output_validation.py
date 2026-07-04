"""MPAS artifact, log, and NetCDF structural validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ....core.netcdf_validation import NetcdfStructureContract, validate_netcdf_structure
from ....core.validation import ValidationReport


@dataclass(frozen=True)
class MpasNetcdfCheck:
    """Associate one MPAS artifact path with a structural NetCDF contract.

    Parameters
    ----------
    path : Path
        Artifact path, relative to the run directory when not absolute.
    contract : NetcdfStructureContract
        Producer-consumer structural expectations.
    """

    path: Path
    contract: NetcdfStructureContract


@dataclass(frozen=True)
class MpasOutputContract:
    """Declare MPAS output, log, and NetCDF validation requirements.

    Parameters
    ----------
    required_files : tuple[Path, ...]
        Required non-empty files, relative to the run directory when not
        absolute.
    log_path : Path | None, default=None
        Optional model log path.
    required_log_markers : tuple[str, ...], default=()
        Markers that must appear in the model log.
    netcdf_checks : tuple[MpasNetcdfCheck, ...], default=()
        Structural checks evaluated after required file presence checks.
    """

    required_files: tuple[Path, ...]
    log_path: Path | None = None
    required_log_markers: tuple[str, ...] = ()
    netcdf_checks: tuple[MpasNetcdfCheck, ...] = ()


def validate_output_contract(run_dir: Path, contract: MpasOutputContract) -> ValidationReport:
    """Validate output existence, log markers, and NetCDF artifact contracts.

    Parameters
    ----------
    run_dir : Path
        MPAS run directory.
    contract : MpasOutputContract
        Required product, log, and structural NetCDF contract.

    Returns
    -------
    ValidationReport
        All observed artifact, marker, and structural findings.
    """
    report = ValidationReport(subject=f"mpas_output:{run_dir}")
    for item in contract.required_files:
        path = item if item.is_absolute() else run_dir / item
        if not path.is_file() or path.stat().st_size == 0:
            report.add("mpas.output_missing", f"Required MPAS output is missing or empty: {path}", path=str(path))

    if contract.log_path is not None:
        log_path = contract.log_path if contract.log_path.is_absolute() else run_dir / contract.log_path
        if not log_path.is_file():
            report.add("mpas.log_missing", f"Required MPAS log is missing: {log_path}", path=str(log_path))
        else:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            for marker in contract.required_log_markers:
                if marker not in text:
                    report.add("mpas.log_marker", f"MPAS log marker is missing: {marker}", path=str(log_path))

    for check in contract.netcdf_checks:
        path = check.path if check.path.is_absolute() else run_dir / check.path
        report.issues.extend(validate_netcdf_structure(path, check.contract).issues)
    return report
