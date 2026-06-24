"""Post-run validation for rendered MONAN-JEDI experiments."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ExperimentConfig, require_key
from .runtime import get_runtime_dir
from .scheduler import load_submission, manifest_path


class RunValidationError(RuntimeError):
    """The scheduler job ended but the scientific run contract was not met."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validation_config(config: ExperimentConfig) -> dict[str, Any]:
    root = require_key(config.validation, "validation", "validation.yaml")
    run = root.get("run", {})
    if not isinstance(run, dict):
        raise TypeError("validation.run must be a mapping when configured.")
    return run


def _resolve_path(runtime_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else runtime_dir / path


def _main_log_candidates(config: ExperimentConfig, job_id: str) -> list[Path]:
    runtime_dir = get_runtime_dir(config).resolve()
    pbs = require_key(config.pbs, "pbs", "pbs.yaml")
    log = pbs.get("log", {})
    if not isinstance(log, dict):
        raise TypeError("pbs.log must be a mapping when configured.")
    directory = _resolve_path(runtime_dir, str(log.get("directory", "logs")))
    filename = str(log.get("filename", "run.${PBS_JOBID}.log"))
    pattern = (
        filename.replace("${PBS_JOBID}", job_id)
        .replace("$PBS_JOBID", job_id)
        .replace("${NP}", "*")
        .replace("$NP", "*")
    )
    return sorted(directory.glob(pattern))


def _write_report(config: ExperimentConfig, report: dict[str, Any]) -> Path:
    path = manifest_path(config).with_name("run-validation.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_run(config: ExperimentConfig) -> Path:
    """Validate the job-specific log and declared runtime products."""
    runtime_dir = get_runtime_dir(config).resolve()
    submission = load_submission(config)
    contract = _validation_config(config)
    required_markers = contract.get("required_log_markers", [])
    warning_markers = contract.get("warning_log_markers", [])
    required_outputs = contract.get("required_outputs", [])

    for field, value in (
        ("validation.run.required_log_markers", required_markers),
        ("validation.run.warning_log_markers", warning_markers),
        ("validation.run.required_outputs", required_outputs),
    ):
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise TypeError(f"{field} must be a list of non-empty strings.")
    if not required_markers:
        raise ValueError("validation.run.required_log_markers cannot be empty.")
    if not required_outputs:
        raise ValueError("validation.run.required_outputs cannot be empty.")

    logs = _main_log_candidates(config, submission.job_id)
    log_path = logs[-1] if logs else None
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path else ""
    missing_markers = [marker for marker in required_markers if marker not in log_text]
    warning_counts = {marker: log_text.count(marker) for marker in warning_markers}

    output_records: list[dict[str, Any]] = []
    missing_outputs: list[str] = []
    for configured_path in required_outputs:
        path = _resolve_path(runtime_dir, configured_path)
        valid = path.is_file() and path.stat().st_size > 0
        output_records.append({
            "configured_path": configured_path,
            "path": str(path),
            "exists": path.exists(),
            "non_empty_file": valid,
            "size_bytes": path.stat().st_size if path.is_file() else None,
        })
        if not valid:
            missing_outputs.append(configured_path)

    valid = log_path is not None and not missing_markers and not missing_outputs
    report = {
        "schema_version": 1,
        "validated_at": _timestamp(),
        "experiment": config.name,
        "job_id": submission.job_id,
        "runtime_dir": str(runtime_dir),
        "valid": valid,
        "main_log": str(log_path) if log_path else None,
        "missing_log_markers": missing_markers,
        "warning_marker_counts": warning_counts,
        "outputs": output_records,
        "missing_outputs": missing_outputs,
    }
    report_path = _write_report(config, report)
    if not valid:
        problems: list[str] = []
        if log_path is None:
            problems.append("main PBS log was not found for the submitted job")
        if missing_markers:
            problems.append("missing log marker(s): " + ", ".join(missing_markers))
        if missing_outputs:
            problems.append("missing or empty output(s): " + ", ".join(missing_outputs))
        raise RunValidationError("Run validation failed: " + "; ".join(problems))

    print(f"[OK] validated run: {report_path}")
    return report_path
