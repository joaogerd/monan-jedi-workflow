"""
Runtime validation module for MONAN-JEDI workflow.

This module validates the runtime environment BEFORE submitting jobs.
Focus: fast-fail, no heavy I/O, no NetCDF reads.
"""

from pathlib import Path
from typing import List


class RuntimeValidationError(Exception):
    pass


def _check_exists(path: Path, errors: List[str], label: str):
    if not path.exists():
        errors.append(f"[MISSING] {label}: {path}")


def _check_executable(path: Path, errors: List[str]):
    if not path.exists():
        errors.append(f"[MISSING] executable: {path}")
    elif not path.is_file():
        errors.append(f"[INVALID] executable is not a file: {path}")
    elif not path.stat().st_mode & 0o111:
        errors.append(f"[INVALID] executable not executable: {path}")


def _check_mpi_layout(nproc: int, errors: List[str]):
    if nproc <= 0:
        errors.append("[INVALID] nproc must be > 0")
    if nproc > 10000:
        errors.append(f"[SUSPICIOUS] nproc very large: {nproc}")


def validate_runtime_contract(config) -> List[str]:
    """
    Validate runtime contract based on loaded ExperimentConfig.

    Returns list of errors. Empty = OK.
    """

    errors: List[str] = []

    # --- Directories ---
    _check_exists(Path(config.paths.input_dir), errors, "input_dir")
    _check_exists(Path(config.paths.output_dir), errors, "output_dir")
    _check_exists(Path(config.paths.work_dir), errors, "work_dir")

    # --- Executable ---
    _check_executable(Path(config.execution.executable), errors)

    # --- MPI layout ---
    _check_mpi_layout(config.execution.nproc, errors)

    return errors


def assert_runtime_ok(config):
    errors = validate_runtime_contract(config)
    if errors:
        msg = "\n".join(errors)
        raise RuntimeValidationError(f"Runtime validation failed:\n{msg}")
