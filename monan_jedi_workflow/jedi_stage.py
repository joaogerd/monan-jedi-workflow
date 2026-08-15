"""Cycle-aware MPAS-JEDI analysis stage with an orchestrator-neutral contract.

Purpose
-------
This module owns *how* a single MPAS-JEDI analysis is prepared, submitted,
observed and validated.  It does not own the workflow DAG.  The same public
operations are therefore usable from a shell, simpleWorkflow, ecFlow, Cylc or a
test harness without changing scientific/runtime logic.

Public stage operations
-----------------------
``prepare_jedi``
    Materialize the runtime for one analysis time, including the background,
    declared links/templates and PBS script.  It never calls ``qsub``.
``submit_jedi``
    Submit an already-prepared PBS script and persist the returned Job ID.
``wait_jedi``
    Observe scheduler completion only.  It does not infer scientific success.
``validate_jedi``
    Check the declared success markers and required products, then publish a
    small artifact manifest for downstream stages/adapters.

Design decisions
----------------
1. ``cycle_time`` means analysis time.  Other timestamps come from
   :mod:`monan_jedi_workflow.analysis_cycle`.
2. The first cycle may consume an external initial background; later cycles may
   consume a forecast produced by the previous cycle.
3. A validated current runtime may be copied from an optional skeleton.  The
   skeleton source is pinned in a local manifest so an existing run directory
   cannot silently mix assets from two baselines.
4. Large scientific inputs are staged with symbolic links.  Real files at a
   declared target are never overwritten.
5. PBS completion and scientific validation are separate states.
6. The stage does not build the B matrix.  B is an external, pre-built input to
   the analysis cycle.

Filesystem contract
-------------------
Internal control files are written below ``<run_dir>/.monan-jedi-workflow``:

``jedi-submission.json``
    Preparation/submission/scheduler state.
``jedi-validation.json``
    Result of the declared scientific/run checks.
``jedi-artifacts.json``
    Validated products with semantic roles such as ``analysis``.
``skeleton.json``
    Provenance of an optional copied runtime skeleton.

The manifests are intentionally ordinary JSON files.  They are not tied to any
workflow engine and can be inspected or consumed by future operational
adapters.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis_cycle import analysis_cycle_context
from .cycle_context import CycleContext, parse_cycle_time
from .scheduler import PBSError, query
from .stage_config import (
    StageConfigurationError,
    load_stage_config,
    render_declared_variables,
    render_text,
    resolve_path,
)

_STAGE_DIR = ".monan-jedi-workflow"
_SUBMISSION_NAME = "jedi-submission.json"
_VALIDATION_NAME = "jedi-validation.json"
_ARTIFACTS_NAME = "jedi-artifacts.json"
_SKELETON_NAME = "skeleton.json"


class JEDIValidationError(RuntimeError):
    """A JEDI run did not satisfy its declared analysis contract."""


@dataclass(frozen=True)
class JEDIRun:
    """Resolved execution model for exactly one analysis cycle.

    The dataclass is immutable so a function cannot accidentally change the
    semantic cycle or filesystem layout halfway through preparation/submission.
    Generated files may of course change on disk.
    """

    cycle: CycleContext
    run_dir: Path
    pbs_path: Path
    manifest_path: Path
    validation_path: Path
    artifacts_path: Path
    config_dir: Path
    config: dict[str, Any]
    context: dict[str, str]
    is_first_cycle: bool


def _timestamp() -> str:
    """Return a normalized UTC timestamp for provenance fields."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    """Validate a configuration mapping and preserve a precise error label."""
    if not isinstance(value, dict):
        raise StageConfigurationError(f"{label} must be a mapping.")
    return value


def _require_list(
    value: Any, label: str, *, non_empty: bool = False
) -> list[Any]:
    """Validate a configuration list."""
    if not isinstance(value, list):
        raise StageConfigurationError(f"{label} must be a list.")
    if non_empty and not value:
        raise StageConfigurationError(f"{label} cannot be empty.")
    return value


def _require_string(value: Any, label: str) -> str:
    """Validate a required non-empty configuration string."""
    if not isinstance(value, str) or not value:
        raise StageConfigurationError(f"{label} must be a non-empty string.")
    return value


def load_jedi_run(config_dir: Path, cycle_time: str) -> JEDIRun:
    """Resolve ``jedi.yaml`` for one analysis time without side effects.

    Parameters
    ----------
    config_dir
        Case directory containing ``jedi.yaml`` and any relative templates.
    cycle_time
        Analysis time in timezone-aware ISO-8601 form.

    Returns
    -------
    JEDIRun
        Fully resolved paths and template context for the requested cycle.

    Raises
    ------
    FileNotFoundError
        If ``jedi.yaml`` does not exist.
    StageConfigurationError
        If required configuration is invalid or uses unknown placeholders.

    Notes
    -----
    This function is safe for preflight/doctor operations because it only reads
    configuration.  It does not check all runtime inputs for existence; those
    checks occur when the corresponding input is actually staged by
    ``prepare_jedi``.
    """
    config_dir = config_dir.resolve()
    config = load_stage_config(config_dir, "jedi.yaml", "jedi")
    cycle = parse_cycle_time(cycle_time)

    cycle_cfg = _require_mapping(config.get("cycle", {}), "jedi.cycle")
    step_hours = int(cycle_cfg.get("step_hours", 6))
    background_offset_hours = int(
        cycle_cfg.get("background_offset_hours", -3)
    )
    window_hours = int(cycle_cfg.get("window_hours", step_hours))

    context = analysis_cycle_context(
        cycle,
        step_hours=step_hours,
        background_offset_hours=background_offset_hours,
        window_hours=window_hours,
    )

    first_cycle_value = cycle_cfg.get("first_cycle")
    if first_cycle_value is None:
        first_cycle = None
    else:
        first_cycle = parse_cycle_time(first_cycle_value).cycle_time
    is_first_cycle = first_cycle is not None and cycle.cycle_time == first_cycle

    # Variables are rendered only after the reserved temporal fields exist.
    # stage_config prevents a case from replacing those reserved names.
    context = render_declared_variables(config, context, label="jedi")

    run_dir = resolve_path(
        _require_string(config.get("run_dir"), "jedi.run_dir"),
        config_dir=config_dir,
        context=context,
        label="jedi.run_dir",
    )
    context = {**context, "run_dir": str(run_dir)}

    pbs = _require_mapping(config.get("pbs"), "jedi.pbs")
    pbs_name = render_text(
        pbs.get("filename", "run_jedi.pbs"),
        context,
        label="jedi.pbs.filename",
    )

    state_dir = run_dir / _STAGE_DIR
    return JEDIRun(
        cycle=cycle,
        run_dir=run_dir,
        pbs_path=run_dir / pbs_name,
        manifest_path=state_dir / _SUBMISSION_NAME,
        validation_path=state_dir / _VALIDATION_NAME,
        artifacts_path=state_dir / _ARTIFACTS_NAME,
        config_dir=config_dir,
        config=config,
        context=context,
        is_first_cycle=is_first_cycle,
    )


def _safe_link(source: Path, target: Path) -> None:
    """Create/update a symlink while refusing to overwrite real data.

    The function is idempotent for an existing link that already resolves to
    the requested source.  A stale symlink may be replaced because the symlink
    itself contains no scientific data.  A regular file/directory is protected
    and causes an explicit failure.
    """
    if not source.exists():
        raise FileNotFoundError(f"JEDI stage source does not exist: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink() and target.resolve() == source.resolve():
            return
        if target.is_symlink():
            target.unlink()
        else:
            raise FileExistsError(
                "JEDI stage refuses to overwrite a non-link target: "
                f"{target}"
            )
    target.symlink_to(source)


def _copy_runtime_skeleton(run: JEDIRun) -> None:
    """Copy an optional validated runtime skeleton exactly once per run dir.

    A skeleton is useful while stabilizing a version-specific MPAS-JEDI
    baseline because several runtime files are resolved relatively rather than
    being fully described by the variational YAML.  Once copied, its absolute
    source is pinned in ``skeleton.json``.

    Reusing the same ``run_dir`` with another skeleton is rejected.  Silent
    mixture of old streams/lookup files with a new executable is much harder to
    diagnose than an early configuration error.
    """
    runtime = _require_mapping(run.config.get("runtime", {}), "jedi.runtime")
    skeleton_value = runtime.get("skeleton")
    if skeleton_value is None:
        return

    source = resolve_path(
        _require_string(skeleton_value, "jedi.runtime.skeleton"),
        config_dir=run.config_dir,
        context=run.context,
        label="jedi.runtime.skeleton",
    )
    if not source.is_dir():
        raise FileNotFoundError(
            f"JEDI runtime skeleton does not exist: {source}"
        )

    marker = run.run_dir / _STAGE_DIR / _SKELETON_NAME
    if marker.is_file():
        try:
            prior = json.loads(marker.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise StageConfigurationError(
                f"Invalid JEDI skeleton manifest: {marker}"
            ) from error
        if prior.get("source") != str(source.resolve()):
            raise StageConfigurationError(
                "JEDI runtime was prepared from a different skeleton; use a "
                "new run_dir instead of silently mixing baselines."
            )
        return

    run.run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, run.run_dir, dirs_exist_ok=True)
    _write_json(
        marker,
        {
            "schema_version": 1,
            "source": str(source.resolve()),
            "copied_at": _timestamp(),
        },
    )


def _render_template(
    source: Path, target: Path, context: dict[str, str]
) -> None:
    """Render a UTF-8 template using only declared ``str.format`` fields."""
    if not source.is_file():
        raise FileNotFoundError(f"JEDI template does not exist: {source}")
    try:
        content = source.read_text(encoding="utf-8").format(**context)
    except KeyError as error:
        raise StageConfigurationError(
            f"JEDI template {source} uses an unknown placeholder: "
            f"{error.args[0]!r}"
        ) from error

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _resolve_background(run: JEDIRun) -> tuple[Path, Path]:
    """Resolve the source/target pair for the analysis background.

    ``initial_source`` is used only when the requested analysis time equals the
    explicitly configured ``jedi.cycle.first_cycle``.  All other cycles use
    ``source``.  This makes the first-cycle exception visible in data rather
    than burying it inside an orchestrator-specific script.
    """
    background = _require_mapping(
        run.config.get("background"), "jedi.background"
    )

    if run.is_first_cycle:
        source_value = background.get("initial_source")
        label = "jedi.background.initial_source"
        if source_value is None:
            raise StageConfigurationError(
                "jedi.background.initial_source is required for "
                "jedi.cycle.first_cycle."
            )
    else:
        source_value = background.get("source")
        label = "jedi.background.source"
        if source_value is None:
            raise StageConfigurationError(
                "jedi.background.source is required for non-initial cycles."
            )

    source = resolve_path(
        _require_string(source_value, label),
        config_dir=run.config_dir,
        context=run.context,
        label=label,
    )

    target_text = render_text(
        _require_string(background.get("target"), "jedi.background.target"),
        run.context,
        label="jedi.background.target",
    )
    target = Path(target_text)
    if not target.is_absolute():
        target = run.run_dir / target
    return source, target


def _render_pbs(run: JEDIRun) -> None:
    """Render a minimal PBS script for the declared analysis command.

    The renderer uses an argv list from YAML and ``shlex.join`` rather than a
    user-provided shell command string.  Environment variables are also
    individually quoted.  This keeps the generated command inspectable and
    avoids accidental shell evaluation while still producing a normal PBS
    script that operations can understand.
    """
    pbs = _require_mapping(run.config.get("pbs"), "jedi.pbs")
    command = _require_list(
        pbs.get("command"), "jedi.pbs.command", non_empty=True
    )
    if any(not isinstance(item, str) or not item for item in command):
        raise StageConfigurationError(
            "jedi.pbs.command must contain non-empty strings."
        )

    queue = render_text(
        pbs.get("queue", "pesqmini"), run.context, label="jedi.pbs.queue"
    )
    walltime = render_text(
        pbs.get("walltime", "00:30:00"),
        run.context,
        label="jedi.pbs.walltime",
    )
    select = int(pbs.get("select", 1))
    ncpus = int(pbs.get("ncpus", pbs.get("mpiprocs", 1)))
    mpiprocs = int(pbs.get("mpiprocs", ncpus))
    launcher = render_text(
        pbs.get("launcher", "mpiexec"),
        run.context,
        label="jedi.pbs.launcher",
    )
    job_name = render_text(
        pbs.get("job_name", "jedi_{cycle_id}"),
        run.context,
        label="jedi.pbs.job_name",
    )
    stdout = render_text(
        pbs.get("stdout", "jedi.stdout.log"),
        run.context,
        label="jedi.pbs.stdout",
    )
    stderr = render_text(
        pbs.get("stderr", "jedi.stderr.log"),
        run.context,
        label="jedi.pbs.stderr",
    )

    environment = _require_mapping(
        pbs.get("environment", {}), "jedi.pbs.environment"
    )
    exports: list[str] = []
    for name, value in environment.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise StageConfigurationError(
                "jedi.pbs.environment must map strings to strings."
            )
        rendered_value = render_text(
            value, run.context, label=f"jedi.pbs.environment.{name}"
        )
        exports.append(f"export {name}={shlex.quote(rendered_value)}")

    rendered_command = shlex.join(
        [
            render_text(
                item, run.context, label="jedi.pbs.command item"
            )
            for item in command
        ]
    )

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
        (
            f"{shlex.quote(launcher)} -n {mpiprocs} {rendered_command} "
            f"> {shlex.quote(stdout)} 2> {shlex.quote(stderr)}"
        ),
        "",
    ]
    run.pbs_path.parent.mkdir(parents=True, exist_ok=True)
    run.pbs_path.write_text("\n".join(lines), encoding="utf-8")
    run.pbs_path.chmod(0o755)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically replace a small JSON control/manifest file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_submission_manifest(run: JEDIRun) -> dict[str, Any]:
    """Load the JEDI submission manifest with stage-specific errors."""
    path = run.manifest_path
    if not path.is_file():
        raise FileNotFoundError(
            "JEDI submission manifest not found. Run 'jedi-prepare' first: "
            f"{path}"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PBSError(f"Invalid JEDI manifest: {path}") from error
    if not isinstance(value, dict):
        raise PBSError(f"JEDI manifest must be a JSON object: {path}")
    return value


def prepare_jedi(config_dir: Path, cycle_time: str) -> JEDIRun:
    """Prepare one analysis runtime without submitting or orchestrating it.

    Side effects
    ------------
    - creates the cycle ``run_dir``;
    - optionally copies the runtime skeleton once;
    - creates/updates declared symbolic links;
    - renders declared templates;
    - writes an executable PBS script;
    - writes ``jedi-submission.json`` with state ``prepared``.

    It does **not** call ``qsub`` and is safe to inspect before submission.
    """
    run = load_jedi_run(config_dir, cycle_time)
    _copy_runtime_skeleton(run)
    run.run_dir.mkdir(parents=True, exist_ok=True)

    background_source, background_target = _resolve_background(run)
    _safe_link(background_source, background_target)

    for index, raw_entry in enumerate(
        _require_list(run.config.get("links", []), "jedi.links")
    ):
        entry = _require_mapping(raw_entry, f"jedi.links[{index}]")
        source = resolve_path(
            entry.get("source"),
            config_dir=run.config_dir,
            context=run.context,
            label=f"jedi.links[{index}].source",
        )
        target_text = render_text(
            entry.get("target"),
            run.context,
            label=f"jedi.links[{index}].target",
        )
        target = Path(target_text)
        if not target.is_absolute():
            target = run.run_dir / target
        _safe_link(source, target)

    for index, raw_entry in enumerate(
        _require_list(run.config.get("templates", []), "jedi.templates")
    ):
        entry = _require_mapping(raw_entry, f"jedi.templates[{index}]")
        source = resolve_path(
            entry.get("source"),
            config_dir=run.config_dir,
            context=run.context,
            label=f"jedi.templates[{index}].source",
        )
        target_text = render_text(
            entry.get("target"),
            run.context,
            label=f"jedi.templates[{index}].target",
        )
        target = Path(target_text)
        if not target.is_absolute():
            target = run.run_dir / target
        _render_template(source, target, run.context)

    _render_pbs(run)
    _write_json(
        run.manifest_path,
        {
            "schema_version": 1,
            "stage": "jedi",
            "cycle_time": run.cycle.cycle_time,
            "cycle_id": run.cycle.cycle_id,
            "prepared_at": _timestamp(),
            "run_dir": str(run.run_dir),
            "pbs_file": str(run.pbs_path),
            "background_source": str(background_source),
            "background_target": str(background_target),
            "state": "prepared",
        },
    )
    print(f"[OK] prepared JEDI analysis cycle: {run.cycle.cycle_time}")
    return run


def submit_jedi(
    config_dir: Path,
    cycle_time: str,
    *,
    resubmit: bool = False,
    wait: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> str:
    """Submit one prepared analysis and persist the PBS Job ID.

    Repeated calls reuse an existing Job ID unless ``resubmit=True``.  This
    conservative default protects a researcher from accidentally creating two
    expensive analyses for the same prepared runtime.
    """
    run = load_jedi_run(config_dir, cycle_time)
    manifest = _read_submission_manifest(run)
    previous_job = manifest.get("job_id")

    if isinstance(previous_job, str) and previous_job and not resubmit:
        job_id = previous_job
        print(f"[SKIP] existing JEDI PBS submission: {job_id}")
    else:
        if not run.pbs_path.is_file():
            raise FileNotFoundError(f"JEDI PBS file not found: {run.pbs_path}")

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
            raise PBSError(
                "JEDI qsub failed with return code "
                f"{process.returncode}: {process.stderr.strip()}"
            )

        lines = [
            line.strip()
            for line in process.stdout.splitlines()
            if line.strip()
        ]
        if not lines:
            raise PBSError("JEDI qsub returned no job identifier.")

        job_id = lines[-1].split()[0]
        manifest.update(
            {
                "job_id": job_id,
                "submitted_at": _timestamp(),
                "state": "submitted",
            }
        )
        _write_json(run.manifest_path, manifest)
        print(f"[OK] submitted JEDI PBS job: {job_id}")

    if wait:
        wait_jedi(
            config_dir,
            cycle_time,
            poll_seconds=poll_seconds,
            timeout_seconds=timeout_seconds,
        )
    return job_id


def wait_jedi(
    config_dir: Path,
    cycle_time: str,
    *,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> str | None:
    """Wait for PBS completion without declaring the analysis scientifically valid."""
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be at least 1.")
    if timeout_seconds is not None and timeout_seconds < 1:
        raise ValueError(
            "timeout_seconds must be at least 1 when provided."
        )

    run = load_jedi_run(config_dir, cycle_time)
    manifest = _read_submission_manifest(run)
    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise PBSError("JEDI run manifest has no submitted job_id.")

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
            _write_json(run.manifest_path, manifest)
            print(f"[OK] JEDI scheduler finished: {job_id}")
            return state or last_state

        if timeout_seconds is not None and elapsed >= timeout_seconds:
            raise TimeoutError(
                f"Timed out after {timeout_seconds}s waiting for JEDI job "
                f"{job_id}."
            )

        last_state = state
        print(
            f"[WAIT] JEDI job={job_id} state={state or 'unknown'} "
            f"elapsed={int(elapsed)}s"
        )
        time.sleep(poll_seconds)


def _output_contract(raw: Any, index: int) -> tuple[str, str]:
    """Normalize a required-output entry to ``(semantic_role, path_template)``."""
    if isinstance(raw, str) and raw:
        return f"output-{index + 1}", raw
    if isinstance(raw, dict):
        role = _require_string(
            raw.get("role", f"output-{index + 1}"),
            f"jedi.validation.required_outputs[{index}].role",
        )
        path = _require_string(
            raw.get("path"),
            f"jedi.validation.required_outputs[{index}].path",
        )
        return role, path
    raise StageConfigurationError(
        "jedi.validation.required_outputs entries must be a path string or "
        "a mapping with role/path."
    )


def validate_jedi(config_dir: Path, cycle_time: str) -> Path:
    """Validate one analysis and publish its orchestrator-neutral artifacts.

    Validation requirements are data, not hidden code.  The case declares log
    markers and required outputs in ``jedi.validation``.  Every required output
    must exist as a non-empty regular file.

    On success, ``jedi-artifacts.json`` records absolute product paths and
    semantic roles.  Downstream adapters may use that small manifest without
    parsing JEDI logs or rediscovering version-specific output names.
    """
    run = load_jedi_run(config_dir, cycle_time)
    manifest = _read_submission_manifest(run)
    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise JEDIValidationError(
            "JEDI validation requires a submitted job manifest."
        )

    validation = _require_mapping(
        run.config.get("validation"), "jedi.validation"
    )
    markers = _require_list(
        validation.get("required_log_markers"),
        "jedi.validation.required_log_markers",
        non_empty=True,
    )
    if any(not isinstance(marker, str) or not marker for marker in markers):
        raise StageConfigurationError(
            "jedi.validation.required_log_markers must contain non-empty "
            "strings."
        )

    raw_outputs = _require_list(
        validation.get("required_outputs"),
        "jedi.validation.required_outputs",
        non_empty=True,
    )

    log_text = render_text(
        validation.get("log", "jedi.stdout.log"),
        run.context,
        label="jedi.validation.log",
    )
    log_path = Path(log_text)
    if not log_path.is_absolute():
        log_path = run.run_dir / log_path
    text = (
        log_path.read_text(encoding="utf-8", errors="replace")
        if log_path.is_file()
        else ""
    )
    missing_markers = [marker for marker in markers if marker not in text]

    missing_outputs: list[str] = []
    artifacts: list[dict[str, Any]] = []
    for index, raw_output in enumerate(raw_outputs):
        role, path_template = _output_contract(raw_output, index)
        rendered = render_text(
            path_template,
            run.context,
            label=f"jedi.validation.required_outputs[{index}]",
        )
        path = Path(rendered)
        if not path.is_absolute():
            path = run.run_dir / path

        exists = path.is_file() and path.stat().st_size > 0
        if not exists:
            missing_outputs.append(rendered)
        artifacts.append(
            {
                "role": role,
                "path": str(path),
                "exists": exists,
            }
        )

    valid = not missing_markers and not missing_outputs
    report = {
        "schema_version": 1,
        "stage": "jedi",
        "cycle_time": run.cycle.cycle_time,
        "cycle_id": run.cycle.cycle_id,
        "job_id": job_id,
        "validated_at": _timestamp(),
        "valid": valid,
        "log": str(log_path),
        "missing_log_markers": missing_markers,
        "missing_outputs": missing_outputs,
    }
    _write_json(run.validation_path, report)

    if not valid:
        details: list[str] = []
        if missing_markers:
            details.append(
                "missing log marker(s): " + ", ".join(missing_markers)
            )
        if missing_outputs:
            details.append(
                "missing output(s): " + ", ".join(missing_outputs)
            )
        raise JEDIValidationError(
            "JEDI validation failed: " + "; ".join(details)
        )

    _write_json(
        run.artifacts_path,
        {
            "schema_version": 1,
            "producer": "monan-jedi-workflow:jedi",
            "cycle_time": run.cycle.cycle_time,
            "cycle_id": run.cycle.cycle_id,
            "created_at": _timestamp(),
            "valid": True,
            "artifacts": artifacts,
        },
    )
    manifest.update(
        {
            "state": "validated",
            "validated_at": _timestamp(),
            "artifacts_manifest": str(run.artifacts_path),
        }
    )
    _write_json(run.manifest_path, manifest)

    print(f"[OK] validated JEDI analysis cycle: {run.validation_path}")
    return run.validation_path
