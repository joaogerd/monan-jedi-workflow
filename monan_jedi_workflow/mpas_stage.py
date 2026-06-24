"""Cycle-aware MPAS forecast preparation, PBS execution and validation.

The stage is intentionally owned by MONAN-JEDI: it knows the MPAS runtime
layout, generated PBS script and products. Higher-level tools only invoke its
public commands and do not need to reproduce this configuration.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .cycle_context import CycleContext, parse_cycle_time
from .scheduler import PBSError, query
from .stage_config import (
    StageConfigurationError,
    cycle_render_context,
    load_stage_config,
    render_text,
    resolve_path,
)


_STAGE_DIR = ".monan-jedi-workflow"
_MANIFEST_NAME = "mpas-submission.json"


@dataclass(frozen=True)
class MPASRun:
    """Resolved filesystem layout for one MPAS cycle."""

    cycle: CycleContext
    run_dir: Path
    pbs_path: Path
    manifest_path: Path
    config_dir: Path
    config: dict[str, Any]
    context: dict[str, str]


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StageConfigurationError(f"{label} must be a mapping.")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise StageConfigurationError(f"{label} must be a list.")
    return value


def _safe_link(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"MPAS stage source does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink() and target.resolve() == source.resolve():
            return
        if target.is_symlink():
            target.unlink()
        else:
            raise FileExistsError(
                "MPAS stage refuses to overwrite a non-link target: " f"{target}"
            )
    target.symlink_to(source)


def _render_template(source: Path, target: Path, context: dict[str, str]) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"MPAS template does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    try:
        rendered = text.format(**context)
    except KeyError as error:
        raise StageConfigurationError(
            f"MPAS template {source} uses an unknown placeholder: {error.args[0]!r}"
        ) from error
    target.write_text(rendered, encoding="utf-8")


def _clean_declared_outputs(run_dir: Path, patterns: list[Any]) -> None:
    for item in patterns:
        if not isinstance(item, str) or not item:
            raise StageConfigurationError("mpas.clean_patterns must contain non-empty strings.")
        for path in run_dir.glob(item):
            if path.is_file() or path.is_symlink():
                path.unlink()


def load_mpas_run(config_dir: Path, cycle_time: str) -> MPASRun:
    """Load ``mpas.yaml`` and resolve all paths for one requested cycle."""
    config_dir = config_dir.resolve()
    config = load_stage_config(config_dir, "mpas.yaml", "mpas")
    cycle = parse_cycle_time(cycle_time)
    lead_hours = int(config.get("lead_hours", 0))
    context = cycle_render_context(cycle, lead_hours=lead_hours)

    run_dir_value = config.get("run_dir")
    if not isinstance(run_dir_value, str) or not run_dir_value:
        raise StageConfigurationError("mpas.run_dir must be a non-empty string.")
    run_dir = resolve_path(
        run_dir_value,
        config_dir=config_dir,
        context=context,
        label="mpas.run_dir",
    )
    context = {**context, "run_dir": str(run_dir)}

    pbs = _require_mapping(config.get("pbs"), "mpas.pbs")
    pbs_name = pbs.get("filename", "run_mpas.pbs")
    if not isinstance(pbs_name, str) or not pbs_name:
        raise StageConfigurationError("mpas.pbs.filename must be a non-empty string.")
    pbs_path = run_dir / render_text(pbs_name, context, label="mpas.pbs.filename")
    manifest_path = run_dir / _STAGE_DIR / _MANIFEST_NAME
    return MPASRun(cycle, run_dir, pbs_path, manifest_path, config_dir, config, context)


def _render_pbs(run: MPASRun) -> None:
    pbs = _require_mapping(run.config.get("pbs"), "mpas.pbs")
    queue = pbs.get("queue")
    walltime = pbs.get("walltime")
    select = int(pbs.get("select", 1))
    ncpus = int(pbs.get("ncpus", pbs.get("mpiprocs", 1)))
    mpiprocs = int(pbs.get("mpiprocs", ncpus))
    launcher = pbs.get("launcher", "mpiexec")
    command = _require_list(pbs.get("command"), "mpas.pbs.command")
    if any(not isinstance(item, str) or not item for item in command):
        raise StageConfigurationError("mpas.pbs.command must contain non-empty strings.")
    if not isinstance(queue, str) or not queue:
        raise StageConfigurationError("mpas.pbs.queue must be a non-empty string.")
    if not isinstance(walltime, str) or not walltime:
        raise StageConfigurationError("mpas.pbs.walltime must be a non-empty string.")
    if not isinstance(launcher, str) or not launcher:
        raise StageConfigurationError("mpas.pbs.launcher must be a non-empty string.")

    environment = pbs.get("environment", {})
    environment = _require_mapping(environment, "mpas.pbs.environment")
    exports: list[str] = []
    for name, value in environment.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise StageConfigurationError("mpas.pbs.environment must map strings to strings.")
        exports.append(f'export {name}="{render_text(value, run.context, label=f"mpas.pbs.environment.{name}")}"')

    rendered_command = " ".join(
        render_text(item, run.context, label="mpas.pbs.command item") for item in command
    )
    output_path = pbs.get("stdout", "stdout.log")
    error_path = pbs.get("stderr", "stderr.log")
    if not isinstance(output_path, str) or not isinstance(error_path, str):
        raise StageConfigurationError("mpas.pbs.stdout and mpas.pbs.stderr must be strings.")

    run.pbs_path.parent.mkdir(parents=True, exist_ok=True)
    run.pbs_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"#PBS -N {pbs.get('job_name', 'mpas_' + run.cycle.cycle_id)}",
                f"#PBS -q {queue}",
                f"#PBS -l select={select}:ncpus={ncpus}:mpiprocs={mpiprocs}",
                f"#PBS -l walltime={walltime}",
                "#PBS -j oe",
                "",
                "set -euo pipefail",
                f"cd {run.run_dir}",
                *exports,
                "ulimit -s unlimited || true",
                f"{launcher} -n {mpiprocs} {rendered_command} > {output_path} 2> {error_path}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    run.pbs_path.chmod(0o755)


def prepare_mpas(config_dir: Path, cycle_time: str) -> MPASRun:
    """Create an idempotent MPAS execution directory for one cycle."""
    run = load_mpas_run(config_dir, cycle_time)
    run.run_dir.mkdir(parents=True, exist_ok=True)
    _clean_declared_outputs(run.run_dir, run.config.get("clean_patterns", []))

    links = _require_list(run.config.get("links", []), "mpas.links")
    for index, entry in enumerate(links):
        entry = _require_mapping(entry, f"mpas.links[{index}]")
        source = resolve_path(
            entry.get("source"),
            config_dir=run.config_dir,
            context=run.context,
            label=f"mpas.links[{index}].source",
        )
        target_value = entry.get("target")
        target_text = render_text(target_value, run.context, label=f"mpas.links[{index}].target")
        target = Path(target_text)
        target = target if target.is_absolute() else run.run_dir / target
        _safe_link(source, target)

    templates = _require_list(run.config.get("templates", []), "mpas.templates")
    for index, entry in enumerate(templates):
        entry = _require_mapping(entry, f"mpas.templates[{index}]")
        source = resolve_path(
            entry.get("source"),
            config_dir=run.config_dir,
            context=run.context,
            label=f"mpas.templates[{index}].source",
        )
        target_text = render_text(
            entry.get("target"), run.context, label=f"mpas.templates[{index}].target"
        )
        target = Path(target_text)
        target = target if target.is_absolute() else run.run_dir / target
        _render_template(source, target, run.context)

    _render_pbs(run)
    manifest = {
        "schema_version": 1,
        "prepared_at": _timestamp(),
        "cycle_time": run.cycle.cycle_time,
        "cycle_id": run.cycle.cycle_id,
        "run_dir": str(run.run_dir),
        "pbs_file": str(run.pbs_path),
        "state": "prepared",
    }
    run.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    run.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] prepared MPAS cycle: {run.cycle.cycle_time}")
    return run


def _load_manifest(run: MPASRun) -> dict[str, Any]:
    if not run.manifest_path.exists():
        raise FileNotFoundError(
            "MPAS run manifest not found. Run 'mpas-prepare' first: " f"{run.manifest_path}"
        )
    value = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PBSError(f"MPAS run manifest must be a JSON object: {run.manifest_path}")
    return value


def _write_manifest(run: MPASRun, value: dict[str, Any]) -> None:
    run.manifest_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def submit_mpas(
    config_dir: Path,
    cycle_time: str,
    *,
    resubmit: bool = False,
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> str:
    """Submit one prepared MPAS cycle and optionally wait for scheduler completion."""
    run = load_mpas_run(config_dir, cycle_time)
    manifest = _load_manifest(run)
    previous_job = manifest.get("job_id")
    if isinstance(previous_job, str) and previous_job and not resubmit:
        print(f"[SKIP] existing MPAS PBS submission: {previous_job}")
        job_id = previous_job
    else:
        if not run.pbs_path.exists():
            raise FileNotFoundError(f"MPAS PBS file not found: {run.pbs_path}")
        process = subprocess.run(
            ["qsub", str(run.pbs_path)],
            cwd=run.run_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        if process.stdout.strip():
            print(process.stdout.strip())
        if process.stderr.strip():
            print(process.stderr.strip())
        if process.returncode != 0:
            raise PBSError(f"MPAS qsub failed with return code {process.returncode}")
        lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
        if not lines:
            raise PBSError("MPAS qsub returned no job identifier.")
        job_id = lines[-1].split()[0]
        manifest.update({"job_id": job_id, "submitted_at": _timestamp(), "state": "submitted"})
        _write_manifest(run, manifest)
        print(f"[OK] submitted MPAS PBS job: {job_id}")

    if wait:
        wait_mpas(config_dir, cycle_time, poll_seconds=poll_seconds, timeout_seconds=timeout_seconds)
    return job_id


def wait_mpas(
    config_dir: Path,
    cycle_time: str,
    *,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> str | None:
    """Wait for an MPAS PBS job; scheduler completion is not model success."""
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be at least 1.")
    run = load_mpas_run(config_dir, cycle_time)
    manifest = _load_manifest(run)
    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise PBSError("MPAS run manifest has no submitted job_id.")
    started = datetime.now(UTC)
    last_state: str | None = None
    while True:
        present, state = query(job_id)
        if not present or state in {"C", "F"}:
            manifest.update({"state": "scheduler-finished", "scheduler_last_state": state or last_state, "scheduler_finished_at": _timestamp()})
            _write_manifest(run, manifest)
            print(f"[OK] MPAS scheduler finished: {job_id}")
            return state or last_state
        last_state = state
        elapsed = int((datetime.now(UTC) - started).total_seconds())
        if timeout_seconds is not None and elapsed >= timeout_seconds:
            raise TimeoutError(f"Timed out after {timeout_seconds}s waiting for MPAS job {job_id}.")
        print(f"[WAIT] MPAS job={job_id} state={state or 'unknown'} elapsed={elapsed}s")
        __import__("time").sleep(poll_seconds)


def validate_mpas(config_dir: Path, cycle_time: str) -> Path:
    """Validate MPAS products declared in ``mpas.validation`` for one cycle."""
    run = load_mpas_run(config_dir, cycle_time)
    validation = _require_mapping(run.config.get("validation", {}), "mpas.validation")
    required_outputs = _require_list(validation.get("required_outputs", []), "mpas.validation.required_outputs")
    log_markers = _require_list(validation.get("required_log_markers", []), "mpas.validation.required_log_markers")
    log_name = validation.get("log", "stdout.log")
    if not isinstance(log_name, str) or not log_name:
        raise StageConfigurationError("mpas.validation.log must be a non-empty string.")
    log_path = run.run_dir / render_text(log_name, run.context, label="mpas.validation.log")
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    missing_markers = [marker for marker in log_markers if marker not in log_text]
    missing_outputs: list[str] = []
    for value in required_outputs:
        path_text = render_text(value, run.context, label="mpas.validation.required_outputs item")
        path = Path(path_text)
        path = path if path.is_absolute() else run.run_dir / path
        if not path.is_file() or path.stat().st_size == 0:
            missing_outputs.append(value)
    report = {
        "validated_at": _timestamp(),
        "cycle_time": run.cycle.cycle_time,
        "cycle_id": run.cycle.cycle_id,
        "valid": not missing_markers and not missing_outputs,
        "log": str(log_path),
        "missing_log_markers": missing_markers,
        "missing_outputs": missing_outputs,
    }
    report_path = run.manifest_path.with_name("mpas-validation.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["valid"]:
        raise RunValidationError(
            "MPAS validation failed: "
            + "; ".join(
                part for part in (
                    "missing log marker(s): " + ", ".join(missing_markers) if missing_markers else "",
                    "missing output(s): " + ", ".join(missing_outputs) if missing_outputs else "",
                ) if part
            )
        )
    print(f"[OK] validated MPAS cycle: {report_path}")
    return report_path


class RunValidationError(RuntimeError):
    """MPAS stage completed but did not satisfy its configured contract."""
