"""PBS submission and waiting for MONAN-JEDI experiments.

Scheduler completion is deliberately distinct from scientific success; callers
must use ``validate-run`` after ``wait``.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ExperimentConfig, require_key
from .runtime import get_rendered_dir, get_runtime_dir

_MANIFEST_DIR = ".monan-jedi-workflow"
_MANIFEST_FILE = "submission.json"
_NOT_FOUND = ("unknown job id", "unknown job", "not found", "does not exist")
_STATE = re.compile(r"^\s*job_state\s*=\s*([A-Za-z])\s*$", re.MULTILINE)


class PBSError(RuntimeError):
    """PBS submission or status query failed."""


@dataclass(frozen=True)
class Submission:
    job_id: str
    manifest_path: Path
    reused: bool = False


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def manifest_path(config: ExperimentConfig) -> Path:
    return get_runtime_dir(config).resolve() / _MANIFEST_DIR / _MANIFEST_FILE


def rendered_pbs_path(config: ExperimentConfig) -> Path:
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    return get_rendered_dir(config).resolve() / f"{experiment['name']}.pbs"


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PBSError(f"Invalid submission manifest: {path}") from error
    if not isinstance(value, dict):
        raise PBSError(f"Submission manifest must be a JSON object: {path}")
    return value


def _write_manifest(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _update_manifest(path: Path, **updates: Any) -> None:
    value = _read_manifest(path)
    value.update(updates)
    _write_manifest(path, value)


def load_submission(config: ExperimentConfig) -> Submission:
    path = manifest_path(config)
    if not path.exists():
        raise FileNotFoundError(
            "No PBS submission manifest exists. Run 'monan-jedi-workflow submit' first: "
            f"{path}"
        )
    value = _read_manifest(path)
    job_id = value.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise PBSError(f"Submission manifest has no valid job_id: {path}")
    return Submission(job_id=job_id, manifest_path=path, reused=True)


def _prepare_log_dir(config: ExperimentConfig, runtime_dir: Path) -> None:
    pbs_config = require_key(config.pbs, "pbs", "pbs.yaml")
    log = pbs_config.get("log", {})
    if not isinstance(log, dict):
        raise TypeError("pbs.log must be a mapping when configured.")
    directory = Path(str(log.get("directory", "logs")))
    (directory if directory.is_absolute() else runtime_dir / directory).mkdir(parents=True, exist_ok=True)


def submit(config: ExperimentConfig, *, resubmit: bool = False) -> Submission:
    """Submit the rendered PBS script and persist its returned job identifier."""
    path = manifest_path(config)
    if path.exists() and not resubmit:
        prior = load_submission(config)
        print(f"[SKIP] existing PBS submission: {prior.job_id}")
        return prior

    runtime_dir = get_runtime_dir(config).resolve()
    pbs_file = rendered_pbs_path(config)
    if not runtime_dir.exists():
        raise FileNotFoundError(f"Runtime directory not found: {runtime_dir}")
    if not pbs_file.exists():
        raise FileNotFoundError("Rendered PBS file not found. Run 'render-pbs' first: " f"{pbs_file}")
    _prepare_log_dir(config, runtime_dir)

    command = ["qsub", str(pbs_file)]
    print("[RUN] " + " ".join(command))
    process = subprocess.run(command, cwd=runtime_dir, text=True, capture_output=True, check=False)
    if process.stdout.strip():
        print(process.stdout.strip())
    if process.stderr.strip():
        print(process.stderr.strip())
    if process.returncode != 0:
        raise PBSError(f"qsub failed with return code {process.returncode}: {pbs_file}")
    lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    if not lines:
        raise PBSError("qsub returned no PBS job identifier.")

    job_id = lines[-1].split()[0]
    _write_manifest(path, {
        "schema_version": 1,
        "experiment": config.name,
        "job_id": job_id,
        "submitted_at": _timestamp(),
        "state": "submitted",
        "pbs_file": str(pbs_file),
        "runtime_dir": str(runtime_dir),
    })
    print(f"[OK] submitted PBS job: {job_id}")
    return Submission(job_id=job_id, manifest_path=path)


def query(job_id: str) -> tuple[bool, str | None]:
    """Return whether a job is visible in qstat and its PBS state when known."""
    process = subprocess.run(["qstat", "-f", job_id], text=True, capture_output=True, check=False)
    text = "\n".join(part for part in (process.stdout.strip(), process.stderr.strip()) if part)
    if process.returncode != 0:
        if any(marker in text.lower() for marker in _NOT_FOUND):
            return False, None
        raise PBSError(f"qstat failed for {job_id} with return code {process.returncode}: {text}")
    match = _STATE.search(process.stdout)
    return True, match.group(1).upper() if match else None


def wait(config: ExperimentConfig, *, poll_seconds: int = 30, timeout_seconds: int | None = None) -> str | None:
    """Wait for scheduler completion without declaring assimilation success."""
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be at least 1.")
    if timeout_seconds is not None and timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1 when provided.")
    submission = load_submission(config)
    started = time.monotonic()
    last_state: str | None = None
    print(f"[WAIT] PBS job: {submission.job_id}")
    while True:
        present, state = query(submission.job_id)
        elapsed = time.monotonic() - started
        if not present or state in {"C", "F"}:
            _update_manifest(submission.manifest_path, state="scheduler-finished", scheduler_last_state=state or last_state, scheduler_finished_at=_timestamp())
            print(f"[OK] PBS scheduler finished: {submission.job_id}")
            return state or last_state
        if timeout_seconds is not None and elapsed >= timeout_seconds:
            _update_manifest(submission.manifest_path, state="wait-timeout", scheduler_last_state=state or last_state)
            raise TimeoutError(f"Timed out after {timeout_seconds}s waiting for PBS job {submission.job_id}.")
        last_state = state
        print(f"[WAIT] job={submission.job_id} state={state or 'unknown'} elapsed={int(elapsed)}s")
        time.sleep(poll_seconds)
