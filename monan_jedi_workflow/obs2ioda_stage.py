"""Operational, cycle-aware Obs2IODA conversion support.

Converter syntax is data-specific and remains declared in ``obs2ioda.yaml``.
This module provides input preflight, tool checks, optional probes, manifests,
logs, provenance and IODA header checks without shell evaluation.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cycle_context import CycleContext, parse_cycle_time
from .stage_config import (
    StageConfigurationError,
    cycle_render_context,
    load_stage_config,
    render_declared_variables,
    render_text,
    resolve_path,
)


class Obs2IODADoctorError(RuntimeError):
    """The configured Obs2IODA environment is not usable."""


class Obs2IODAValidationError(RuntimeError):
    """A converter product does not satisfy its declared IODA contract."""


@dataclass(frozen=True)
class Obs2IODARun:
    cycle: CycleContext
    work_dir: Path
    manifest_path: Path
    config_dir: Path
    config: dict[str, Any]
    context: dict[str, str]


@dataclass(frozen=True)
class ToolCheck:
    command: str
    resolved_path: str | None
    executable: bool


@dataclass(frozen=True)
class RuntimeLinkerCheck:
    executable: str
    resolved_executable: str | None
    returncode: int | None
    resolved_libraries: list[dict[str, Any]]
    missing_libraries: list[str]
    valid: bool
    problem: str | None = None


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_list(value: Any, label: str, *, non_empty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        raise StageConfigurationError(f"{label} must be a list.")
    if non_empty and not value:
        raise StageConfigurationError(f"{label} cannot be empty.")
    return value


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StageConfigurationError(f"{label} must be a mapping.")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise StageConfigurationError(f"{label} must be a non-empty string.")
    return value


def _timeout(value: Any, label: str, default: int) -> int:
    value = default if value is None else value
    if not isinstance(value, int) or value < 1:
        raise StageConfigurationError(f"{label} must be a positive integer.")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_record(path: Path, *, include_sha256: bool) -> dict[str, Any]:
    record: dict[str, Any] = {"path": str(path), "exists": path.exists(), "is_file": path.is_file()}
    if path.is_file():
        stat = path.stat()
        record.update({
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        })
        if include_sha256:
            record["sha256"] = _sha256(path)
    return record


def _config_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _tool_check(command: str) -> ToolCheck:
    candidate = Path(command).expanduser()
    if candidate.is_absolute() or "/" in command:
        resolved = candidate.resolve() if candidate.exists() else None
    else:
        found = shutil.which(command)
        resolved = Path(found).resolve() if found else None
    return ToolCheck(command, str(resolved) if resolved else None, bool(resolved and os.access(resolved, os.X_OK)))


def _provenance_options(config: dict[str, Any]) -> dict[str, bool]:
    raw = _require_mapping(config.get("provenance", {}), "obs2ioda.provenance")
    sha256 = raw.get("sha256", False)
    if not isinstance(sha256, bool):
        raise StageConfigurationError("obs2ioda.provenance.sha256 must be a boolean.")
    return {"sha256": sha256}


def _render_runtime(run: Obs2IODARun) -> dict[str, Any]:
    raw = _require_mapping(run.config.get("runtime", {}), "obs2ioda.runtime")
    library_paths = _require_list(
        raw.get("library_paths", []), "obs2ioda.runtime.library_paths"
    )
    dependency_checks = _require_list(
        raw.get("dependency_checks", []), "obs2ioda.runtime.dependency_checks"
    )
    if any(not isinstance(item, str) or not item for item in library_paths):
        raise StageConfigurationError(
            "obs2ioda.runtime.library_paths must contain non-empty strings."
        )
    if any(not isinstance(item, str) or not item for item in dependency_checks):
        raise StageConfigurationError(
            "obs2ioda.runtime.dependency_checks must contain non-empty strings."
        )
    rendered_paths = [
        str(
            resolve_path(
                item,
                config_dir=run.config_dir,
                context=run.context,
                label="obs2ioda.runtime.library_paths item",
            )
        )
        for item in library_paths
    ]
    return {
        "library_paths": rendered_paths,
        "dependency_checks": [
            render_text(item, run.context, label="obs2ioda.runtime.dependency_checks item")
            for item in dependency_checks
        ],
        "linker_command": render_text(
            _require_string(
                raw.get("linker_command", "ldd"), "obs2ioda.runtime.linker_command"
            ),
            run.context,
            label="obs2ioda.runtime.linker_command",
        ),
        "timeout_seconds": _timeout(
            raw.get("timeout_seconds"), "obs2ioda.runtime.timeout_seconds", 30
        ),
    }


def _runtime_environment(runtime: dict[str, Any]) -> dict[str, str]:
    """Build an environment used only by Obs2IODA child processes."""
    environment = os.environ.copy()
    configured = [str(item) for item in runtime.get("library_paths", [])]
    inherited = environment.get("LD_LIBRARY_PATH", "").split(os.pathsep)
    paths = list(dict.fromkeys(item for item in configured + inherited if item))
    if paths:
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(paths)
    return environment


def _parse_ldd(output: str) -> tuple[list[dict[str, Any]], list[str]]:
    resolved: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=>" in line:
            name, target = (part.strip() for part in line.split("=>", 1))
            target_path = target.split(" (", 1)[0].strip()
            found = target_path != "not found"
            resolved.append(
                {"library": name, "path": target_path if found else None, "found": found}
            )
            if not found:
                missing.append(name)
        else:
            target_path = line.split(" (", 1)[0].strip()
            resolved.append(
                {"library": Path(target_path).name, "path": target_path, "found": True}
            )
    return resolved, missing


def _check_runtime_dependencies(
    runtime: dict[str, Any], *, cwd: Path, logs_dir: Path, label: str
) -> list[RuntimeLinkerCheck]:
    checks: list[RuntimeLinkerCheck] = []
    environment = _runtime_environment(runtime)
    linker = _tool_check(str(runtime.get("linker_command", "ldd")))
    for index, executable_text in enumerate(runtime.get("dependency_checks", []), start=1):
        executable = _tool_check(str(executable_text))
        if not linker.executable:
            checks.append(
                RuntimeLinkerCheck(
                    str(executable_text), executable.resolved_path, None, [], [], False,
                    f"runtime linker command unavailable: {linker.command}",
                )
            )
            continue
        if not executable.executable:
            checks.append(
                RuntimeLinkerCheck(
                    str(executable_text), executable.resolved_path, None, [], [], False,
                    "runtime dependency executable unavailable",
                )
            )
            continue
        try:
            process = subprocess.run(
                [str(linker.resolved_path), str(executable.resolved_path)],
                cwd=cwd,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
                timeout=_timeout(
                    runtime.get("timeout_seconds"), "obs2ioda runtime timeout", 30
                ),
            )
        except subprocess.TimeoutExpired as error:
            (logs_dir / f"{label}-linker-{index}.stdout.log").write_text(
                error.stdout or "", encoding="utf-8"
            )
            (logs_dir / f"{label}-linker-{index}.stderr.log").write_text(
                error.stderr or "", encoding="utf-8"
            )
            checks.append(
                RuntimeLinkerCheck(
                    str(executable_text), executable.resolved_path, None, [], [], False,
                    "runtime linker check timeout",
                )
            )
            continue
        (logs_dir / f"{label}-linker-{index}.stdout.log").write_text(process.stdout, encoding="utf-8")
        (logs_dir / f"{label}-linker-{index}.stderr.log").write_text(process.stderr, encoding="utf-8")
        resolved, missing = _parse_ldd(process.stdout + "\n" + process.stderr)
        valid = process.returncode == 0 and not missing
        checks.append(
            RuntimeLinkerCheck(
                str(executable_text), executable.resolved_path, process.returncode,
                resolved, missing, valid,
                None if valid else "unresolved runtime linker dependencies",
            )
        )
    return checks


def load_obs2ioda_run(config_dir: Path, cycle_time: str) -> Obs2IODARun:
    """Load ``obs2ioda.yaml`` and resolve a cycle-specific work directory."""
    config_dir = config_dir.resolve()
    config = load_stage_config(config_dir, "obs2ioda.yaml", "obs2ioda")
    cycle = parse_cycle_time(cycle_time)
    context = render_declared_variables(config, cycle_render_context(cycle), label="obs2ioda")
    work_dir = resolve_path(
        _require_string(config.get("work_dir"), "obs2ioda.work_dir"),
        config_dir=config_dir,
        context=context,
        label="obs2ioda.work_dir",
    )
    return Obs2IODARun(
        cycle=cycle,
        work_dir=work_dir,
        manifest_path=work_dir / ".monan-jedi-workflow" / "obs2ioda.json",
        config_dir=config_dir,
        config=config,
        context={**context, "work_dir": str(work_dir)},
    )


def _render_argv(value: Any, context: dict[str, str], label: str) -> list[str]:
    argv = _require_list(value, label, non_empty=True)
    if any(not isinstance(item, str) or not item for item in argv):
        raise StageConfigurationError(f"{label} must contain non-empty strings.")
    return [render_text(item, context, label=f"{label} item") for item in argv]


def _render_inspection(run: Obs2IODARun, converter: dict[str, Any], output: Path) -> dict[str, Any]:
    global_cfg = _require_mapping(run.config.get("inspection", {}), "obs2ioda.inspection")
    validation = _require_mapping(converter.get("validation", {}), f"obs2ioda converter '{converter['name']}'.validation")
    local_cfg = _require_mapping(validation.get("inspection", {}), f"obs2ioda converter '{converter['name']}'.validation.inspection")
    argv = local_cfg.get("argv", global_cfg.get("argv"))
    if argv is None:
        raise StageConfigurationError("Obs2IODA validation requires inspection.argv globally or per converter.")
    markers = _require_list(
        validation.get("required_header_markers", global_cfg.get("required_header_markers", [])),
        "obs2ioda inspection.required_header_markers",
    )
    if any(not isinstance(item, str) or not item for item in markers):
        raise StageConfigurationError("Obs2IODA header markers must be non-empty strings.")
    return {
        "argv": _render_argv(argv, {**run.context, "output": str(output)}, "obs2ioda inspection.argv"),
        "required_header_markers": markers,
        "timeout_seconds": _timeout(local_cfg.get("timeout_seconds", global_cfg.get("timeout_seconds")), "obs2ioda inspection.timeout_seconds", 60),
    }


def _render_converter(run: Obs2IODARun, entry: dict[str, Any], index: int) -> dict[str, Any]:
    name = _require_string(entry.get("name"), f"obs2ioda.converters[{index}].name")
    inputs = _require_list(entry.get("inputs", []), f"obs2ioda.converters[{index}].inputs")
    outputs = _require_list(entry.get("outputs"), f"obs2ioda.converters[{index}].outputs", non_empty=True)
    if any(not isinstance(item, str) or not item for item in inputs + outputs):
        raise StageConfigurationError(f"obs2ioda.converters[{index}] paths must be non-empty strings.")
    converter = {
        "name": name,
        "argv": _render_argv(entry.get("argv"), run.context, f"obs2ioda.converters[{index}].argv"),
        "inputs": [str(resolve_path(item, config_dir=run.config_dir, context=run.context, label=f"obs2ioda.converters[{index}].inputs item")) for item in inputs],
        "outputs": [str(resolve_path(item, config_dir=run.config_dir, context=run.context, label=f"obs2ioda.converters[{index}].outputs item")) for item in outputs],
        "timeout_seconds": _timeout(entry.get("timeout_seconds", run.config.get("timeout_seconds")), f"obs2ioda.converters[{index}].timeout_seconds", 900),
        "validation": entry.get("validation", {}),
    }
    converter["plan_sha256"] = _config_sha256(converter)
    return converter


def _render_probe(run: Obs2IODARun, entry: dict[str, Any], index: int) -> dict[str, Any]:
    name = _require_string(entry.get("name"), f"obs2ioda.probes[{index}].name")
    markers = _require_list(entry.get("required_output_markers", []), f"obs2ioda.probes[{index}].required_output_markers")
    if any(not isinstance(item, str) or not item for item in markers):
        raise StageConfigurationError("Obs2IODA probe markers must be non-empty strings.")
    return {
        "name": name,
        "argv": _render_argv(entry.get("argv"), run.context, f"obs2ioda.probes[{index}].argv"),
        "required_output_markers": markers,
        "timeout_seconds": _timeout(entry.get("timeout_seconds"), f"obs2ioda.probes[{index}].timeout_seconds", 30),
    }


def _build_plan(run: Obs2IODARun) -> dict[str, Any]:
    converters = [_render_converter(run, _require_mapping(item, f"obs2ioda.converters[{index}]"), index) for index, item in enumerate(_require_list(run.config.get("converters"), "obs2ioda.converters", non_empty=True))]
    probes = [_render_probe(run, _require_mapping(item, f"obs2ioda.probes[{index}]"), index) for index, item in enumerate(_require_list(run.config.get("probes", []), "obs2ioda.probes"))]
    plan = {
        "cycle_time": run.cycle.cycle_time,
        "cycle_id": run.cycle.cycle_id,
        "work_dir": str(run.work_dir),
        "converters": converters,
        "probes": probes,
        "provenance": _provenance_options(run.config),
        "runtime": _render_runtime(run),
    }
    plan["plan_sha256"] = _config_sha256(plan)
    return plan


def _load_manifest(run: Obs2IODARun) -> dict[str, Any]:
    if not run.manifest_path.exists():
        raise FileNotFoundError(f"Obs2IODA manifest not found. Run 'obs2ioda-prepare' first: {run.manifest_path}")
    try:
        payload = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StageConfigurationError(f"Invalid Obs2IODA manifest: {run.manifest_path}") from error
    if not isinstance(payload, dict):
        raise StageConfigurationError(f"Obs2IODA manifest must be a JSON object: {run.manifest_path}")
    return payload


def _write_manifest(run: Obs2IODARun, payload: dict[str, Any]) -> None:
    run.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = run.manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(run.manifest_path)


def _run_probe(run: Obs2IODARun, probe: dict[str, Any], logs_dir: Path) -> dict[str, Any]:
    name = probe["name"]
    stdout_path = logs_dir / f"doctor-{name}.stdout.log"
    stderr_path = logs_dir / f"doctor-{name}.stderr.log"
    tool = _tool_check(probe["argv"][0])
    record: dict[str, Any] = {"name": name, "argv": probe["argv"], "tool": tool.__dict__, "stdout": str(stdout_path), "stderr": str(stderr_path)}
    if not tool.executable:
        return {**record, "valid": False, "problem": "probe executable unavailable"}
    try:
        process = subprocess.run(probe["argv"], cwd=run.work_dir, env=_runtime_environment(_render_runtime(run)), text=True, capture_output=True, check=False, timeout=probe["timeout_seconds"])
    except subprocess.TimeoutExpired as error:
        stdout_path.write_text(error.stdout or "", encoding="utf-8")
        stderr_path.write_text(error.stderr or "", encoding="utf-8")
        return {**record, "valid": False, "problem": "probe timeout"}
    stdout_path.write_text(process.stdout, encoding="utf-8")
    stderr_path.write_text(process.stderr, encoding="utf-8")
    missing = [marker for marker in probe["required_output_markers"] if marker not in process.stdout + "\n" + process.stderr]
    return {**record, "returncode": process.returncode, "missing_output_markers": missing, "valid": process.returncode == 0 and not missing}


def doctor_obs2ioda(config_dir: Path, cycle_time: str) -> Path:
    """Verify configured tools and run optional, explicitly declared probes."""
    run = load_obs2ioda_run(config_dir, cycle_time)
    run.work_dir.mkdir(parents=True, exist_ok=True)
    plan = _build_plan(run)
    logs_dir = run.work_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    linker_checks = _check_runtime_dependencies(
        plan["runtime"], cwd=run.work_dir, logs_dir=logs_dir, label="doctor"
    )
    for check in linker_checks:
        if not check.valid:
            detail = ", ".join(check.missing_libraries) or check.problem or "unknown error"
            problems.append(f"runtime dependencies unavailable for {check.executable}: {detail}")
    for converter in plan["converters"]:
        tool = _tool_check(converter["argv"][0])
        checks.append({"role": f"converter:{converter['name']}", **tool.__dict__})
        if not tool.executable:
            problems.append(f"converter executable unavailable: {tool.command}")
        for output in converter["outputs"]:
            inspector = _tool_check(_render_inspection(run, converter, Path(output))["argv"][0])
            checks.append({"role": f"inspector:{converter['name']}", **inspector.__dict__})
            if not inspector.executable:
                problems.append(f"inspection executable unavailable: {inspector.command}")
    probes = [_run_probe(run, probe, logs_dir) for probe in plan["probes"]]
    problems.extend(f"probe failed: {probe['name']}" for probe in probes if not probe["valid"])
    report = {"schema_version": 3, "checked_at": _timestamp(), "cycle_time": run.cycle.cycle_time, "cycle_id": run.cycle.cycle_id, "plan_sha256": plan["plan_sha256"], "checks": checks, "runtime": {"library_paths": plan["runtime"]["library_paths"], "linker_checks": [check.__dict__ for check in linker_checks]}, "probes": probes, "valid": not problems, "problems": problems}
    report_path = run.work_dir / ".monan-jedi-workflow" / "obs2ioda-doctor.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if problems:
        raise Obs2IODADoctorError("Obs2IODA doctor failed: " + "; ".join(problems))
    print(f"[OK] Obs2IODA doctor: {report_path}")
    return report_path


def prepare_obs2ioda(config_dir: Path, cycle_time: str, *, refresh: bool = False) -> Obs2IODARun:
    """Preflight inputs and persist an immutable conversion plan for one cycle."""
    run = load_obs2ioda_run(config_dir, cycle_time)
    run.work_dir.mkdir(parents=True, exist_ok=True)
    plan = _build_plan(run)
    include_sha256 = plan["provenance"]["sha256"]
    input_records = {converter["name"]: [_file_record(Path(path), include_sha256=include_sha256) for path in converter["inputs"]] for converter in plan["converters"]}
    missing = [record["path"] for records in input_records.values() for record in records if not record["is_file"]]
    if missing:
        raise FileNotFoundError("Obs2IODA input(s) missing: " + ", ".join(missing))
    if run.manifest_path.exists():
        existing = _load_manifest(run)
        if existing.get("plan_sha256") == plan["plan_sha256"] and not refresh:
            print(f"[SKIP] existing Obs2IODA plan: {run.cycle.cycle_time}")
            return run
        if existing.get("state") in {"converted", "validated"}:
            raise StageConfigurationError("Obs2IODA products already exist for a previous plan. Use a new output directory or explicit version instead of replacing provenance.")
    _write_manifest(run, {"schema_version": 3, "prepared_at": _timestamp(), "state": "prepared", **plan, "input_records": input_records, "runs": [], "validations": []})
    print(f"[OK] prepared Obs2IODA cycle: {run.cycle.cycle_time}")
    return run


def _outputs_complete(outputs: list[str]) -> bool:
    return all(Path(path).is_file() and Path(path).stat().st_size > 0 for path in outputs)


def run_obs2ioda(config_dir: Path, cycle_time: str, *, force: bool = False) -> Path:
    """Run declared converters while preserving logs and provenance per attempt."""
    run = load_obs2ioda_run(config_dir, cycle_time)
    manifest = _load_manifest(run)
    converters = _require_list(manifest.get("converters"), "obs2ioda manifest converters", non_empty=True)
    include_sha256 = bool(_require_mapping(manifest.get("provenance", {}), "obs2ioda manifest provenance").get("sha256", False))
    logs_dir = run.work_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    runtime = _require_mapping(manifest.get("runtime", {}), "obs2ioda manifest runtime")
    linker_checks = _check_runtime_dependencies(
        runtime, cwd=run.work_dir, logs_dir=logs_dir, label="run"
    )
    failed_linker_checks = [check for check in linker_checks if not check.valid]
    manifest["runtime_dependency_checks"] = [check.__dict__ for check in linker_checks]
    if failed_linker_checks:
        manifest["state"] = "failed-runtime-dependencies"
        _write_manifest(run, manifest)
        details = "; ".join(
            f"{check.executable}: {', '.join(check.missing_libraries) or check.problem}"
            for check in failed_linker_checks
        )
        raise Obs2IODADoctorError("Obs2IODA runtime dependency check failed: " + details)
    child_environment = _runtime_environment(runtime)
    for converter in converters:
        converter = _require_mapping(converter, "obs2ioda manifest converter")
        name = _require_string(converter.get("name"), "obs2ioda manifest converter name")
        outputs = _require_list(converter.get("outputs"), f"{name}.outputs", non_empty=True)
        if _outputs_complete(outputs) and not force:
            print(f"[SKIP] Obs2IODA converter already produced outputs: {name}")
            continue
        for output in outputs:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
        attempt = len(manifest.get("runs", [])) + 1
        stdout_path = logs_dir / f"{name}.attempt-{attempt}.stdout.log"
        stderr_path = logs_dir / f"{name}.attempt-{attempt}.stderr.log"
        started_at = _timestamp()
        try:
            process = subprocess.run(converter["argv"], cwd=run.work_dir, env=child_environment, text=True, capture_output=True, check=False, timeout=_timeout(converter.get("timeout_seconds"), f"{name}.timeout_seconds", 900))
        except subprocess.TimeoutExpired as error:
            stdout_path.write_text(error.stdout or "", encoding="utf-8")
            stderr_path.write_text(error.stderr or "", encoding="utf-8")
            manifest.update({"state": "failed", "failed_converter": name})
            manifest.setdefault("runs", []).append({"name": name, "attempt": attempt, "started_at": started_at, "finished_at": _timestamp(), "timeout": True})
            _write_manifest(run, manifest)
            raise RuntimeError(f"Obs2IODA converter '{name}' timed out.") from error
        stdout_path.write_text(process.stdout, encoding="utf-8")
        stderr_path.write_text(process.stderr, encoding="utf-8")
        records = [_file_record(Path(path), include_sha256=include_sha256) for path in outputs]
        manifest.setdefault("runs", []).append({"name": name, "attempt": attempt, "argv": converter["argv"], "started_at": started_at, "finished_at": _timestamp(), "returncode": process.returncode, "stdout": str(stdout_path), "stderr": str(stderr_path), "outputs": records})
        if process.returncode != 0:
            manifest.update({"state": "failed", "failed_converter": name})
            _write_manifest(run, manifest)
            raise RuntimeError(f"Obs2IODA converter '{name}' failed with return code {process.returncode}.")
        if any(not record["is_file"] or record.get("size_bytes", 0) == 0 for record in records):
            manifest.update({"state": "invalid-output", "failed_converter": name})
            _write_manifest(run, manifest)
            raise RuntimeError(f"Obs2IODA converter '{name}' did not create all declared outputs.")
        _write_manifest(run, manifest)
        print(f"[OK] Obs2IODA converter: {name}")
    manifest.update({"state": "converted", "converted_at": _timestamp()})
    _write_manifest(run, manifest)
    print(f"[OK] completed Obs2IODA conversion: {run.cycle.cycle_time}")
    return run.manifest_path


def validate_obs2ioda(config_dir: Path, cycle_time: str) -> Path:
    """Inspect every declared IODA product and enforce header markers."""
    run = load_obs2ioda_run(config_dir, cycle_time)
    manifest = _load_manifest(run)
    converters = _require_list(manifest.get("converters"), "obs2ioda manifest converters", non_empty=True)
    logs_dir = run.work_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    child_environment = _runtime_environment(
        _require_mapping(manifest.get("runtime", {}), "obs2ioda manifest runtime")
    )
    records: list[dict[str, Any]] = []
    problems: list[str] = []
    for converter in converters:
        converter = _require_mapping(converter, "obs2ioda manifest converter")
        name = _require_string(converter.get("name"), "obs2ioda manifest converter name")
        for index, output_text in enumerate(_require_list(converter.get("outputs"), f"{name}.outputs", non_empty=True)):
            output = Path(output_text)
            record: dict[str, Any] = {"converter": name, "output": _file_record(output, include_sha256=False)}
            if not record["output"]["is_file"] or record["output"].get("size_bytes", 0) == 0:
                record.update({"valid": False, "problem": "missing or empty output"})
                records.append(record)
                problems.append(f"{name}: {output}")
                continue
            inspection = _render_inspection(run, converter, output)
            stdout_path = logs_dir / f"{name}.inspect-{index + 1}.stdout.log"
            stderr_path = logs_dir / f"{name}.inspect-{index + 1}.stderr.log"
            try:
                process = subprocess.run(inspection["argv"], cwd=run.work_dir, env=child_environment, text=True, capture_output=True, check=False, timeout=inspection["timeout_seconds"])
                stdout_path.write_text(process.stdout, encoding="utf-8")
                stderr_path.write_text(process.stderr, encoding="utf-8")
                missing = [marker for marker in inspection["required_header_markers"] if marker not in process.stdout + "\n" + process.stderr]
                record.update({"inspection_argv": inspection["argv"], "inspection_returncode": process.returncode, "inspection_stdout": str(stdout_path), "inspection_stderr": str(stderr_path), "missing_header_markers": missing, "valid": process.returncode == 0 and not missing})
                if not record["valid"]:
                    problems.append(f"{name}: invalid IODA header for {output}")
            except subprocess.TimeoutExpired as error:
                stdout_path.write_text(error.stdout or "", encoding="utf-8")
                stderr_path.write_text(error.stderr or "", encoding="utf-8")
                record.update({"valid": False, "problem": "inspection timeout"})
                problems.append(f"{name}: IODA inspection timed out for {output}")
            records.append(record)
    report = {"schema_version": 2, "validated_at": _timestamp(), "cycle_time": run.cycle.cycle_time, "cycle_id": run.cycle.cycle_id, "plan_sha256": manifest.get("plan_sha256"), "valid": not problems, "records": records, "problems": problems}
    report_path = run.manifest_path.with_name("obs2ioda-validation.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest.setdefault("validations", []).append({"validated_at": report["validated_at"], "valid": report["valid"], "report": str(report_path)})
    manifest["state"] = "validated" if report["valid"] else "invalid"
    _write_manifest(run, manifest)
    if problems:
        raise Obs2IODAValidationError("Obs2IODA validation failed: " + "; ".join(problems))
    print(f"[OK] validated Obs2IODA cycle: {report_path}")
    return report_path
