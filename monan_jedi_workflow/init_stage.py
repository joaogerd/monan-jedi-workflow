"""MPAS initial-condition stage built on the MPAS PBS conventions."""
from __future__ import annotations

import json
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
    pbs_path = run_dir / render_text(
        config["pbs"].get("filename", "run_mpas_init.pbs"),
        context,
        label="mpas_init.pbs.filename",
    )
    return InitRun(
        cycle,
        run_dir,
        pbs_path,
        run_dir / ".monan-jedi-workflow" / "mpas-init.json",
        config_dir,
        config,
        context,
    )


def _save(run: InitRun, data: dict[str, Any]) -> None:
    run.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = run.manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(run.manifest_path)


def _read(run: InitRun) -> dict[str, Any]:
    if not run.manifest_path.is_file():
        raise FileNotFoundError(f"MPAS init manifest not found: {run.manifest_path}")
    try:
        value = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PBSError(f"Invalid MPAS init manifest: {run.manifest_path}") from error
    if not isinstance(value, dict):
        raise PBSError(f"MPAS init manifest must be a JSON object: {run.manifest_path}")
    return value


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
    _save(
        run,
        {
            "schema_version": 1,
            "cycle_time": run.cycle.cycle_time,
            "cycle_id": run.cycle.cycle_id,
            "run_dir": str(run.run_dir),
            "pbs_file": str(run.pbs_path),
            "state": "prepared",
            "prepared_at": _timestamp(),
        },
    )
    print(f"[OK] prepared MPAS init cycle: {run.cycle.cycle_time}")
    return run


def submit_mpas_init(
    config_dir: Path,
    cycle_time: str,
    *,
    wait: bool = False,
    poll_seconds: int = 30,
    resubmit: bool = False,
) -> str:
    run = _load(config_dir, cycle_time)
    manifest = _read(run)
    job_id = None if resubmit else manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        if not run.pbs_path.is_file():
            raise FileNotFoundError(f"MPAS init PBS file not found: {run.pbs_path}")
        result = subprocess.run(["qsub", str(run.pbs_path)], cwd=run.run_dir, text=True, capture_output=True, check=False)
        if result.returncode:
            raise PBSError(result.stderr.strip() or "MPAS init qsub failed")
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise PBSError("MPAS init qsub returned no job identifier")
        job_id = lines[-1].split()[0]
        manifest.update({"job_id": job_id, "state": "submitted", "submitted_at": _timestamp()})
        _save(run, manifest)
        print(f"[OK] submitted MPAS init PBS job: {job_id}")
    else:
        print(f"[SKIP] existing MPAS init PBS submission: {job_id}")
    if wait:
        wait_mpas_init(config_dir, cycle_time, poll_seconds=poll_seconds)
    return job_id


def wait_mpas_init(config_dir: Path, cycle_time: str, *, poll_seconds: int = 30) -> None:
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be at least 1")
    run = _load(config_dir, cycle_time)
    manifest = _read(run)
    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise PBSError("MPAS init manifest has no submitted job_id")
    while True:
        present, state = query(job_id)
        if not present or state in {"C", "F"}:
            manifest.update(
                {
                    "state": "scheduler-finished",
                    "scheduler_finished_at": _timestamp(),
                    "scheduler_last_state": state,
                }
            )
            _save(run, manifest)
            print(f"[OK] MPAS init scheduler finished: {job_id}")
            return
        time.sleep(poll_seconds)


def validate_mpas_init(config_dir: Path, cycle_time: str) -> Path:
    """Validate non-empty init products in the actual PBS run directory."""
    run = _load(config_dir, cycle_time)
    manifest = _read(run)
    spec = run.config["validation"]
    declared_log = Path(render_text(spec.get("log", "stdout.log"), run.context, label="mpas_init.validation.log"))
    log = declared_log if declared_log.is_absolute() else run.run_dir / declared_log
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    missing_markers = [marker for marker in spec.get("required_log_markers", []) if marker not in text]
    missing_outputs: list[str] = []
    for declared in spec["required_outputs"]:
        rendered = Path(render_text(declared, run.context, label="mpas_init.validation.output"))
        output = rendered if rendered.is_absolute() else run.run_dir / rendered
        if not output.is_file() or output.stat().st_size == 0:
            missing_outputs.append(str(output))
    report = {
        "schema_version": 1,
        "validated_at": _timestamp(),
        "cycle_time": run.cycle.cycle_time,
        "job_id": manifest.get("job_id"),
        "valid": not missing_markers and not missing_outputs,
        "missing_log_markers": missing_markers,
        "missing_outputs": missing_outputs,
    }
    path = run.manifest_path.with_name("mpas-init-validation.json")
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["valid"]:
        raise RuntimeError(f"MPAS init validation failed: {report}")
    print(f"[OK] validated MPAS init cycle: {path}")
    return path
