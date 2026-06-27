"""Cycle-aware WPS/UNGRIB preparation, execution and validation.

This module never downloads GRIB data and never builds WPS.  It consumes the
WPS tools published by MONAN-JEDI and transforms one declared GRIB input into
the WPS intermediate file required by ``mpas_init_atmosphere``.
"""

from __future__ import annotations

import json
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


_STAGE_DIR = ".monan-jedi-workflow"
_MANIFEST_NAME = "wps.json"


class WPSValidationError(RuntimeError):
    """WPS did not produce its declared intermediate file."""


@dataclass(frozen=True)
class WPSRun:
    cycle: CycleContext
    work_dir: Path
    manifest_path: Path
    config_dir: Path
    config: dict[str, Any]
    context: dict[str, str]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StageConfigurationError(f"{label} must be a mapping.")
    return value


def _list(value: Any, label: str, *, non_empty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        raise StageConfigurationError(f"{label} must be a list.")
    if non_empty and not value:
        raise StageConfigurationError(f"{label} cannot be empty.")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise StageConfigurationError(f"{label} must be a non-empty string.")
    return value


def _context(cycle: CycleContext) -> dict[str, str]:
    return {
        **cycle_render_context(cycle),
        "wps_time": cycle.value.strftime("%Y-%m-%d_%H"),
    }


def load_wps_run(config_dir: Path, cycle_time: str) -> WPSRun:
    """Load ``wps.yaml`` and resolve one cycle-specific WPS working directory."""
    config_dir = config_dir.resolve()
    config = load_stage_config(config_dir, "wps.yaml", "wps")
    cycle = parse_cycle_time(cycle_time)
    context = render_declared_variables(config, _context(cycle), label="wps")
    work_dir = resolve_path(
        _string(config.get("work_dir"), "wps.work_dir"),
        config_dir=config_dir,
        context=context,
        label="wps.work_dir",
    )
    return WPSRun(
        cycle=cycle,
        work_dir=work_dir,
        manifest_path=work_dir / _STAGE_DIR / _MANIFEST_NAME,
        config_dir=config_dir,
        config=config,
        context={**context, "work_dir": str(work_dir)},
    )


def _safe_link(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"WPS stage source does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink() and target.resolve() == source.resolve():
            return
        if target.is_symlink():
            target.unlink()
        else:
            raise FileExistsError(f"WPS stage refuses to overwrite a non-link target: {target}")
    target.symlink_to(source)


def _render_template(source: Path, target: Path, context: dict[str, str]) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"WPS template does not exist: {source}")
    try:
        content = source.read_text(encoding="utf-8").format(**context)
    except KeyError as error:
        raise StageConfigurationError(
            f"WPS template {source} uses an unknown placeholder: {error.args[0]!r}"
        ) from error
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _clean(run: WPSRun) -> None:
    for raw_pattern in _list(run.config.get("clean_patterns", []), "wps.clean_patterns"):
        pattern = _string(raw_pattern, "wps.clean_patterns item")
        for path in run.work_dir.glob(pattern):
            if path.is_file() or path.is_symlink():
                path.unlink()


def _render_argv(value: Any, context: dict[str, str], label: str) -> list[str]:
    raw = _list(value, label, non_empty=True)
    if any(not isinstance(item, str) or not item for item in raw):
        raise StageConfigurationError(f"{label} must contain non-empty strings.")
    return [render_text(item, context, label=f"{label} item") for item in raw]


def _write_manifest(run: WPSRun, payload: dict[str, Any]) -> None:
    run.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = run.manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(run.manifest_path)


def _load_manifest(run: WPSRun) -> dict[str, Any]:
    if not run.manifest_path.is_file():
        raise FileNotFoundError(f"WPS manifest not found. Run 'wps-prepare' first: {run.manifest_path}")
    try:
        payload = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StageConfigurationError(f"Invalid WPS manifest: {run.manifest_path}") from error
    if not isinstance(payload, dict):
        raise StageConfigurationError(f"WPS manifest must be a JSON object: {run.manifest_path}")
    return payload


def prepare_wps(config_dir: Path, cycle_time: str) -> WPSRun:
    """Stage declared WPS tools, GRIB link and rendered namelist for one cycle."""
    run = load_wps_run(config_dir, cycle_time)
    run.work_dir.mkdir(parents=True, exist_ok=True)
    _clean(run)

    for index, raw in enumerate(_list(run.config.get("links", []), "wps.links")):
        entry = _mapping(raw, f"wps.links[{index}]")
        source = resolve_path(
            _string(entry.get("source"), f"wps.links[{index}].source"),
            config_dir=run.config_dir,
            context=run.context,
            label=f"wps.links[{index}].source",
        )
        target_name = render_text(
            _string(entry.get("target"), f"wps.links[{index}].target"),
            run.context,
            label=f"wps.links[{index}].target",
        )
        target = Path(target_name)
        _safe_link(source, target if target.is_absolute() else run.work_dir / target)

    for index, raw in enumerate(_list(run.config.get("templates", []), "wps.templates")):
        entry = _mapping(raw, f"wps.templates[{index}]")
        source = resolve_path(
            _string(entry.get("source"), f"wps.templates[{index}].source"),
            config_dir=run.config_dir,
            context=run.context,
            label=f"wps.templates[{index}].source",
        )
        target_name = render_text(
            _string(entry.get("target"), f"wps.templates[{index}].target"),
            run.context,
            label=f"wps.templates[{index}].target",
        )
        target = Path(target_name)
        _render_template(source, target if target.is_absolute() else run.work_dir / target, run.context)

    execution = _mapping(run.config.get("run"), "wps.run")
    link_argv = _render_argv(execution.get("link_grib_argv"), run.context, "wps.run.link_grib_argv")
    ungrib_argv = _render_argv(execution.get("ungrib_argv"), run.context, "wps.run.ungrib_argv")
    validation = _mapping(run.config.get("validation"), "wps.validation")
    outputs = _list(validation.get("required_outputs"), "wps.validation.required_outputs", non_empty=True)
    rendered_outputs = [
        str(resolve_path(_string(item, "wps.validation.required_outputs item"), config_dir=run.config_dir, context=run.context, label="wps.validation.required_outputs item"))
        for item in outputs
    ]

    _write_manifest(
        run,
        {
            "schema_version": 1,
            "prepared_at": _timestamp(),
            "cycle_time": run.cycle.cycle_time,
            "cycle_id": run.cycle.cycle_id,
            "work_dir": str(run.work_dir),
            "link_grib_argv": link_argv,
            "ungrib_argv": ungrib_argv,
            "required_outputs": rendered_outputs,
            "state": "prepared",
        },
    )
    print(f"[OK] prepared WPS cycle: {run.cycle.cycle_time}")
    return run


def run_wps(config_dir: Path, cycle_time: str, *, force: bool = False) -> Path:
    """Run link_grib and ungrib without shell evaluation."""
    run = load_wps_run(config_dir, cycle_time)
    manifest = _load_manifest(run)
    outputs = [Path(item) for item in manifest.get("required_outputs", [])]
    if outputs and all(path.is_file() and path.stat().st_size > 0 for path in outputs) and not force:
        print(f"[SKIP] WPS outputs already exist for cycle: {run.cycle.cycle_time}")
        return run.manifest_path

    logs = run.work_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for name, argv in (("link_grib", manifest["link_grib_argv"]), ("ungrib", manifest["ungrib_argv"])):
        result = subprocess.run(argv, cwd=run.work_dir, text=True, capture_output=True, check=False)
        (logs / f"{name}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (logs / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
        if result.returncode != 0:
            manifest.update({"state": "failed", "failed_step": name, "finished_at": _timestamp()})
            _write_manifest(run, manifest)
            raise RuntimeError(f"WPS {name} failed with return code {result.returncode}.")

    manifest.update({"state": "completed", "completed_at": _timestamp()})
    _write_manifest(run, manifest)
    print(f"[OK] completed WPS cycle: {run.cycle.cycle_time}")
    return run.manifest_path


def validate_wps(config_dir: Path, cycle_time: str) -> Path:
    """Validate declared WPS intermediate outputs and optional ungrib markers."""
    run = load_wps_run(config_dir, cycle_time)
    manifest = _load_manifest(run)
    validation = _mapping(run.config.get("validation"), "wps.validation")
    outputs = [Path(item) for item in manifest.get("required_outputs", [])]
    missing = [str(path) for path in outputs if not path.is_file() or path.stat().st_size == 0]

    log_name = render_text(validation.get("log", "logs/ungrib.stdout.log"), run.context, label="wps.validation.log")
    log_path = Path(log_name)
    log_path = log_path if log_path.is_absolute() else run.work_dir / log_path
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    markers = _list(validation.get("required_log_markers", []), "wps.validation.required_log_markers")
    missing_markers = [
        _string(marker, "wps.validation.required_log_markers item")
        for marker in markers
        if _string(marker, "wps.validation.required_log_markers item") not in log_text
    ]

    report = {
        "schema_version": 1,
        "validated_at": _timestamp(),
        "cycle_time": run.cycle.cycle_time,
        "cycle_id": run.cycle.cycle_id,
        "valid": not missing and not missing_markers,
        "log": str(log_path),
        "missing_outputs": missing,
        "missing_log_markers": missing_markers,
    }
    report_path = run.manifest_path.with_name("wps-validation.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["valid"]:
        raise WPSValidationError(
            "WPS validation failed: "
            + "; ".join(
                part
                for part in (
                    "missing output(s): " + ", ".join(missing) if missing else "",
                    "missing log marker(s): " + ", ".join(missing_markers) if missing_markers else "",
                )
                if part
            )
        )
    print(f"[OK] validated WPS cycle: {report_path}")
    return report_path
