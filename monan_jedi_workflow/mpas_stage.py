"""Cycle-aware MPAS forecast preparation, PBS execution and validation."""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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


class MPASValidationError(RuntimeError):
    """MPAS execution did not satisfy its declared run contract."""


@dataclass(frozen=True)
class MPASRun:
    """Resolved filesystem layout for a single cycle-specific MPAS run."""

    cycle: CycleContext
    run_dir: Path
    pbs_path: Path
    manifest_path: Path
    config_dir: Path
    config: dict[str, Any]
    context: dict[str, str]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StageConfigurationError(f"{label} must be a mapping.")
    return value


def _require_list(value: Any, label: str, *, non_empty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        raise StageConfigurationError(f"{label} must be a list.")
    if non_empty and not value:
        raise StageConfigurationError(f"{label} cannot be empty.")
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
    try:
        content = source.read_text(encoding="utf-8").format(**context)
    except KeyError as error:
        raise StageConfigurationError(
            f"MPAS template {source} uses an unknown placeholder: {error.args[0]!r}"
        ) from error
    if target.is_file() and target.read_text(encoding="utf-8") == content:
        return
    target.write_text(content, encoding="utf-8")


def _clean_declared_outputs(run_dir: Path, patterns: list[Any]) -> None:
    for item in patterns:
        if not isinstance(item, str) or not item:
            raise StageConfigurationError("mpas.clean_patterns must contain non-empty strings.")
        for path in run_dir.glob(item):
            if path.is_file() or path.is_symlink():
                path.unlink()


def _resolve_lead_hours(config: dict[str, Any], lead_hours: int | None) -> int:
    configured = int(config.get("lead_hours", 0))
    resolved = configured if lead_hours is None else int(lead_hours)
    if resolved < 0:
        raise StageConfigurationError("mpas.lead_hours must not be negative.")
    return resolved


def load_mpas_run(
    config_dir: Path,
    cycle_time: str,
    *,
    lead_hours: int | None = None,
) -> MPASRun:
    """Load ``mpas.yaml`` and resolve one cycle/lead-specific execution layout.

    ``lead_hours`` is an explicit runtime override intended for NMC f024/f048
    campaigns. When omitted, the value declared in ``mpas.yaml`` is preserved.
    """
    config_dir = config_dir.resolve()
    config = load_stage_config(config_dir, "mpas.yaml", "mpas")
    cycle = parse_cycle_time(cycle_time)
    resolved_lead = _resolve_lead_hours(config, lead_hours)
    context = cycle_render_context(cycle, lead_hours=resolved_lead)

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
    pbs_path = run_dir / render_text(pbs_name, context, label="mpas.pbs.filename")
    return MPASRun(
        cycle=cycle,
        run_dir=run_dir,
        pbs_path=pbs_path,
        manifest_path=run_dir / _STAGE_DIR / _MANIFEST_NAME,
        config_dir=config_dir,
        config=config,
        context=context,
    )


def _render_pbs(run: MPASRun) -> None:
    pbs = _require_mapping(run.config.get("pbs"), "mpas.pbs")
    queue = render_text(pbs.get("queue"), run.context, label="mpas.pbs.queue")
    walltime = render_text(pbs.get("walltime"), run.context, label="mpas.pbs.walltime")
    select = int(pbs.get("select", 1))
    ncpus = int(pbs.get("ncpus", pbs.get("mpiprocs", 1)))
    mpiprocs = int(pbs.get("mpiprocs", ncpus))
    launcher = render_text(pbs.get("launcher", "mpiexec"), run.context, label="mpas.pbs.launcher")
    command = _require_list(pbs.get("command"), "mpas.pbs.command", non_empty=True)
    if any(not isinstance(item, str) or not item for item in command):
        raise StageConfigurationError("mpas.pbs.command must contain non-empty strings.")

    environment = _require_mapping(pbs.get("environment", {}), "mpas.pbs.environment")
    exports: list[str] = []
    for name, value in environment.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise StageConfigurationError("mpas.pbs.environment must map strings to strings.")
        exports.append(
            f"export {name}={shlex.quote(render_text(value, run.context, label=f'mpas.pbs.environment.{name}'))}"
        )

    job_name = render_text(
        pbs.get("job_name", "mpas_{cycle_id}"), run.context, label="mpas.pbs.job_name"
    )
    stdout = render_text(pbs.get("stdout", "stdout.log"), run.context, label="mpas.pbs.stdout")
    stderr = render_text(pbs.get("stderr", "stderr.log"), run.context, label="mpas.pbs.stderr")
    rendered_command = shlex.join(
        [render_text(item, run.context, label="mpas.pbs.command item") for item in command]
    )

    run.pbs_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "#!/usr/bin/env bash",
        f"#PBS -N {job_name}",
        f"#PBS -q {queue}",
        f"#PBS -l select={select}:ncpus={ncpus}:mpiprocs={mpiprocs}",
        f"#PBS -l walltime={walltime}",
        "#PBS -j oe",
        "",
        "set -euo pipefail",
        f"cd {shlex.quote(str(run.run_dir))}",
        *exports,
        "ulimit -s unlimited || true",
        f"{shlex.quote(launcher)} -n {mpiprocs} {rendered_command} > {shlex.quote(stdout)} 2> {shlex.quote(stderr)}",
        "",
    ]
    run.pbs_path.write_text("\n".join(lines), encoding="utf-8")
    run.pbs_path.chmod(0o755)


def prepare_mpas(
    config_dir: Path,
    cycle_time: str,
    *,
    lead_hours: int | None = None,
    force: bool = False,
) -> MPASRun:
    """Stage links/templates and render PBS for one MPAS cycle/lead.

    Declared output cleanup is intentionally opt-in through ``force``; repeated
    preparation must not delete an otherwise valid forecast product.
    """
    run = load_mpas_run(config_dir, cycle_time, lead_hours=lead_hours)
    run.run_dir.mkdir(parents=True, exist_ok=True)
    if force:
        _clean_declared_outputs(run.run_dir, run.config.get("clean_patterns", []))

    for index, raw_entry in enumerate(_require_list(run.config.get("links", []), "mpas.links")):
        entry = _require_mapping(raw_entry, f"mpas.links[{index}]")
        source = resolve_path(
            entry.get("source"),
            config_dir=run.config_dir,
            context=run.context,
            label=f"mpas.links[{index}].source",
        )
        target_text = render_text(entry.get("target"), run.context, label=f"mpas.links[{index}].target")
        target = Path(target_text)
        _safe_link(source, target if target.is_absolute() else run.run_dir / target)

    for index, raw_entry in enumerate(_require_list(run.config.get("templates", []), "mpas.templates")):
        entry = _require_mapping(raw_entry, f"mpas.templates[{index}]")
        source = resolve_path(
            entry.get("source"),
            config_dir=run.config_dir,
            context=run.context,
            label=f"mpas.templates[{index}].source",
        )
        target_text = render_text(entry.get("target"), run.context, label=f"mpas.templates[{index}].target")
        target = Path(target_text)
        _render_template(source, target if target.is_absolute() else run.run_dir / target, run.context)

    _render_pbs(run)
    _write_manifest(
        run,
        {
            "schema_version": 1,
            "prepared_at": _timestamp(),
            "cycle_time": run.cycle.cycle_time,
            "cycle_id": run.cycle.cycle_id,
            "lead_hours": int(run.context["lead_hours"]),
            "run_dir": str(run.run_dir),
            "pbs_file": str(run.pbs_path),
            "state": "prepared",
        },
    )
    print(f"[OK] prepared MPAS cycle: {run.cycle.cycle_time} lead={run.context['lead_hours']}h")
    return run


def _load_manifest(run: MPASRun) -> dict[str, Any]:
    if not run.manifest_path.exists():
        raise FileNotFoundError(
            "MPAS run manifest not found. Run 'mpas-prepare' first: " f"{run.manifest_path}"
        )
    try:
        value = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PBSError(f"Invalid MPAS run manifest: {run.manifest_path}") from error
    if not isinstance(value, dict):
        raise PBSError(f"MPAS run manifest must be a JSON object: {run.manifest_path}")
    return value


def _write_manifest(run: MPASRun, value: dict[str, Any]) -> None:
    run.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = run.manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(run.manifest_path)


def submit_mpas(
    config_dir: Path,
    cycle_time: str,
    *,
    lead_hours: int | None = None,
    resubmit: bool = False,
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> str:
    """Submit a prepared MPAS cycle/lead and optionally wait for PBS completion."""
    run = load_mpas_run(config_dir, cycle_time, lead_hours=lead_hours)
    manifest = _load_manifest(run)
    previous_job = manifest.get("job_id")
    if isinstance(previous_job, str) and previous_job and not resubmit:
        job_id = previous_job
        print(f"[SKIP] existing MPAS PBS submission: {job_id}")
    else:
        if not run.pbs_path.is_file():
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
        wait_mpas(
            config_dir,
            cycle_time,
            lead_hours=lead_hours,
            poll_seconds=poll_seconds,
            timeout_seconds=timeout_seconds,
        )
    return job_id


def wait_mpas(
    config_dir: Path,
    cycle_time: str,
    *,
    lead_hours: int | None = None,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> str | None:
    """Wait for scheduler completion without declaring MPAS scientific success."""
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be at least 1.")
    if timeout_seconds is not None and timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1 when provided.")
    run = load_mpas_run(config_dir, cycle_time, lead_hours=lead_hours)
    manifest = _load_manifest(run)
    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise PBSError("MPAS run manifest has no submitted job_id.")

    started = time.monotonic()
    last_state: str | None = None
    while True:
        present, state = query(job_id)
        elapsed = time.monotonic() - started
        if not present or state in {"C", "F"}:
            manifest.update(
                {
                    "state": "scheduler-finished",
                    "scheduler_last_state": state or last_state,
                    "scheduler_finished_at": _timestamp(),
                }
            )
            _write_manifest(run, manifest)
            print(f"[OK] MPAS scheduler finished: {job_id}")
            return state or last_state
        if timeout_seconds is not None and elapsed >= timeout_seconds:
            raise TimeoutError(f"Timed out after {timeout_seconds}s waiting for MPAS job {job_id}.")
        last_state = state
        print(f"[WAIT] MPAS job={job_id} state={state or 'unknown'} elapsed={int(elapsed)}s")
        time.sleep(poll_seconds)


def validate_mpas(
    config_dir: Path,
    cycle_time: str,
    *,
    lead_hours: int | None = None,
) -> Path:
    """Validate the MPAS log and products declared for one submitted cycle/lead."""
    run = load_mpas_run(config_dir, cycle_time, lead_hours=lead_hours)
    manifest = _load_manifest(run)
    if not isinstance(manifest.get("job_id"), str) or not manifest["job_id"]:
        raise MPASValidationError("MPAS validation requires a submitted job manifest.")

    validation = _require_mapping(run.config.get("validation"), "mpas.validation")
    required_outputs = _require_list(
        validation.get("required_outputs"), "mpas.validation.required_outputs", non_empty=True
    )
    log_markers = _require_list(
        validation.get("required_log_markers"), "mpas.validation.required_log_markers", non_empty=True
    )
    if any(not isinstance(item, str) or not item for item in required_outputs + log_markers):
        raise StageConfigurationError(
            "mpas.validation outputs and markers must contain non-empty strings."
        )
    log_name = render_text(validation.get("log", "stdout.log"), run.context, label="mpas.validation.log")
    log_path = Path(log_name)
    log_path = log_path if log_path.is_absolute() else run.run_dir / log_path
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
        "schema_version": 1,
        "validated_at": _timestamp(),
        "cycle_time": run.cycle.cycle_time,
        "cycle_id": run.cycle.cycle_id,
        "lead_hours": int(run.context["lead_hours"]),
        "job_id": manifest["job_id"],
        "valid": not missing_markers and not missing_outputs,
        "log": str(log_path),
        "missing_log_markers": missing_markers,
        "missing_outputs": missing_outputs,
    }
    report_path = run.manifest_path.with_name("mpas-validation.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["valid"]:
        details = []
        if missing_markers:
            details.append("missing log marker(s): " + ", ".join(missing_markers))
        if missing_outputs:
            details.append("missing output(s): " + ", ".join(missing_outputs))
        raise MPASValidationError("MPAS validation failed: " + "; ".join(details))
    print(f"[OK] validated MPAS cycle: {report_path}")
    return report_path
