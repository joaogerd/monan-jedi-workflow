"""MPAS initial-condition stage built on the MPAS PBS conventions."""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cycle_context import parse_cycle_time
from .mpas_stage import _clean_declared_outputs, _render_pbs, _render_template, _safe_link, _timestamp
from .scheduler import PBSError, query
from .stage_config import cycle_render_context, load_stage_config, render_declared_variables, render_text, resolve_path


@dataclass(frozen=True)
class InitRun:
    cycle: Any
    run_dir: Path
    pbs_path: Path
    manifest_path: Path
    config_dir: Path
    config: dict[str, Any]
    context: dict[str, str]


def _load(config_dir: Path, cycle_time: str) -> InitRun:
    config_dir = config_dir.resolve()
    config = load_stage_config(config_dir, "mpas_init.yaml", "mpas_init")
    cycle = parse_cycle_time(cycle_time)
    context = render_declared_variables(config, cycle_render_context(cycle), label="mpas_init")
    run_dir = resolve_path(config["run_dir"], config_dir=config_dir, context=context, label="mpas_init.run_dir")
    context = {**context, "run_dir": str(run_dir)}
    pbs_path = run_dir / render_text(config["pbs"].get("filename", "run_mpas_init.pbs"), context, label="mpas_init.pbs.filename")
    return InitRun(cycle, run_dir, pbs_path, run_dir / ".monan-jedi-workflow" / "mpas-init.json", config_dir, config, context)


def _save(run: InitRun, data: dict[str, Any]) -> None:
    run.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temp = run.manifest_path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(run.manifest_path)


def _read(run: InitRun) -> dict[str, Any]:
    if not run.manifest_path.is_file():
        raise FileNotFoundError(f"MPAS init manifest not found: {run.manifest_path}")
    return json.loads(run.manifest_path.read_text(encoding="utf-8"))


def prepare_mpas_init(config_dir: Path, cycle_time: str) -> InitRun:
    run = _load(config_dir, cycle_time)
    run.run_dir.mkdir(parents=True, exist_ok=True)
    _clean_declared_outputs(run.run_dir, run.config.get("clean_patterns", []))
    for entry in run.config.get("links", []):
        source = resolve_path(entry["source"], config_dir=run.config_dir, context=run.context, label="mpas_init.links.source")
        target = Path(render_text(entry["target"], run.context, label="mpas_init.links.target"))
        _safe_link(source, target if target.is_absolute() else run.run_dir / target)
    for entry in run.config.get("templates", []):
        source = resolve_path(entry["source"], config_dir=run.config_dir, context=run.context, label="mpas_init.templates.source")
        target = Path(render_text(entry["target"], run.context, label="mpas_init.templates.target"))
        _render_template(source, target if target.is_absolute() else run.run_dir / target, run.context)
    _render_pbs(run)
    _save(run, {"schema_version": 1, "cycle_time": run.cycle.cycle_time, "cycle_id": run.cycle.cycle_id, "run_dir": str(run.run_dir), "pbs_file": str(run.pbs_path), "state": "prepared", "prepared_at": _timestamp()})
    print(f"[OK] prepared MPAS init cycle: {run.cycle.cycle_time}")
    return run


def submit_mpas_init(config_dir: Path, cycle_time: str, *, wait: bool = False, poll_seconds: int = 30, resubmit: bool = False) -> str:
    run = _load(config_dir, cycle_time)
    manifest = _read(run)
    job_id = None if resubmit else manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        result = subprocess.run(["qsub", str(run.pbs_path)], cwd=run.run_dir, text=True, capture_output=True, check=False)
        if result.returncode:
            raise PBSError(result.stderr.strip() or "MPAS init qsub failed")
        job_id = result.stdout.strip().splitlines()[-1].split()[0]
        manifest.update({"job_id": job_id, "state": "submitted", "submitted_at": _timestamp()})
        _save(run, manifest)
        print(f"[OK] submitted MPAS init PBS job: {job_id}")
    if wait:
        wait_mpas_init(config_dir, cycle_time, poll_seconds=poll_seconds)
    return job_id


def wait_mpas_init(config_dir: Path, cycle_time: str, *, poll_seconds: int = 30) -> None:
    """Wait for PBS and require a confirmed successful terminal Exit_status.

    A missing qstat job or terminal state alone is NOT proof of successful
    execution. Never report scientific success without checking outputs.
    """
    run = _load(config_dir, cycle_time)
    manifest = _read(run)
    job_id = manifest["job_id"]
    while True:
        present, state = query(job_id)
        if not present or state in {"C", "F", "X"}:
            # PBS can retire the active record before the history is available.
            # Do not assume that this means success.
            history = subprocess.run(
                ["qstat", "-x", "-f", job_id], cwd=run.run_dir,
                capture_output=True, text=True, check=False
            )
            if history.returncode != 0:
                manifest.update({
                    "state": "scheduler-unconfirmed",
                    "scheduler_finished_at": _timestamp(),
                    "scheduler_last_state": state,
                    "scheduler_history_error": history.stderr.strip(),
                })
                _save(run, manifest)
                raise PBSError(
                    f"MPAS Init job {job_id} ended or disappeared but its PBS "
                    "Exit_status could not be verified; inspect qstat -x -f "
                    f"{job_id} before retrying."
                )
            result = re.search(r"(?m)^\s*Exit_status\s*=\s*(-?\d+)\s*$", history.stdout)
            if result is None:
                manifest.update({
                    "state": "scheduler-unconfirmed",
                    "scheduler_finished_at": _timestamp(),
                    "scheduler_last_state": state,
                    "scheduler_history_excerpt": history.stdout[-1500:],
                })
                _save(run, manifest)
                raise PBSError(
                    f"MPAS Init job {job_id}: PBS history does not provide "
                    "Exit_status; refusing to assume success."
                )
            exit_status = int(result.group(1))
            manifest.update({
                "state": "scheduler-finished" if exit_status == 0 else "scheduler-failed",
                "scheduler_finished_at": _timestamp(),
                "scheduler_last_state": state,
                "pbs_exit_status": exit_status,
            })
            _save(run, manifest)
            if exit_status != 0:
                raise PBSError(
                    f"MPAS Init job {job_id} failed with PBS Exit_status={exit_status}; "
                    f"inspect stdout/stderr under {run.run_dir}."
                )
            print(f"[OK] MPAS init PBS job {job_id} completed with Exit_status=0")
            return
        time.sleep(poll_seconds)


def validate_mpas_init(config_dir: Path, cycle_time: str) -> Path:
    run = _load(config_dir, cycle_time)
    manifest = _read(run)
    spec = run.config["validation"]
    log = run.run_dir / render_text(spec.get("log", "stdout.log"), run.context, label="mpas_init.validation.log")
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    missing_markers = [m for m in spec.get("required_log_markers", []) if m not in text]
    missing_outputs = [str(resolve_path(path, config_dir=run.config_dir, context=run.context, label="mpas_init.validation.output")) for path in spec["required_outputs"] if not resolve_path(path, config_dir=run.config_dir, context=run.context, label="mpas_init.validation.output").is_file()]
    report = {"cycle_time": run.cycle.cycle_time, "job_id": manifest.get("job_id"), "valid": not missing_markers and not missing_outputs, "missing_log_markers": missing_markers, "missing_outputs": missing_outputs}
    path = run.manifest_path.with_name("mpas-init-validation.json")
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["valid"]:
        raise RuntimeError(f"MPAS init validation failed: {report}")
    print(f"[OK] validated MPAS init cycle: {path}")
    return path
