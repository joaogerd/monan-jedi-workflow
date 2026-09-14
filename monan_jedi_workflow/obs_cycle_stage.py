"""Cycle-safe wrappers around Obs2IODA for multi-day campaigns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .obs2ioda_stage import (
    _build_plan,
    _config_sha256,
    _file_record,
    _load_manifest,
    _write_manifest,
    doctor_obs2ioda,
    load_obs2ioda_run,
    prepare_obs2ioda,
    run_obs2ioda,
)
from .obs_cycle_inputs import InputResolution, resolve_cycle_input


def _resolve_plan(run, plan: dict[str, Any]) -> tuple[dict[str, Any], list[InputResolution]]:
    resolutions: list[InputResolution] = []
    for converter in plan.get("converters", []):
        if not isinstance(converter, dict):
            continue
        name = str(converter.get("name", "converter"))
        replacements: dict[str, str] = {}
        resolved_inputs: list[str] = []
        for value in converter.get("inputs", []):
            original = Path(str(value))
            resolved, record = resolve_cycle_input(original, run.cycle, name)
            resolved_inputs.append(str(resolved))
            if resolved != original:
                replacements[str(original)] = str(resolved)
            if record is not None:
                resolutions.append(record)
        converter["inputs"] = resolved_inputs
        if replacements:
            converter["argv"] = [
                replacements.get(str(item), str(item)) for item in converter.get("argv", [])
            ]
        payload = {k: v for k, v in converter.items() if k != "plan_sha256"}
        converter["plan_sha256"] = _config_sha256(payload)
    payload = {k: v for k, v in plan.items() if k != "plan_sha256"}
    plan["plan_sha256"] = _config_sha256(payload)
    return plan, resolutions


def check_obs_cycle_sources(config_dir: Path, cycle_time: str) -> list[InputResolution]:
    run = load_obs2ioda_run(config_dir, cycle_time)
    _, resolutions = _resolve_plan(run, _build_plan(run))
    return resolutions


def _repair_manifest(config_dir: Path, cycle_time: str) -> list[InputResolution]:
    run = load_obs2ioda_run(config_dir, cycle_time)
    manifest = _load_manifest(run)
    if manifest.get("state") == "validated":
        return []
    plan = {
        key: manifest[key]
        for key in ("cycle_time", "cycle_id", "work_dir", "converters", "probes", "provenance", "runtime")
        if key in manifest
    }
    plan, resolutions = _resolve_plan(run, plan)
    if not resolutions:
        return []
    manifest["converters"] = plan["converters"]
    manifest["plan_sha256"] = plan["plan_sha256"]
    include_sha256 = bool(manifest.get("provenance", {}).get("sha256", False))
    manifest["input_records"] = {
        converter["name"]: [
            _file_record(Path(path), include_sha256=include_sha256)
            for path in converter.get("inputs", [])
        ]
        for converter in manifest.get("converters", [])
    }
    manifest.setdefault("input_resolutions", []).extend(item.as_dict() for item in resolutions)
    manifest["state"] = "prepared"
    _write_manifest(run, manifest)
    return resolutions


def doctor_obs2ioda_resolved(config_dir: Path, cycle_time: str) -> Path:
    resolutions = check_obs_cycle_sources(config_dir, cycle_time)
    for item in resolutions:
        print(f"[OBS] source available for {item.cycle}: {item.resolved}")
    return doctor_obs2ioda(config_dir, cycle_time)


def prepare_obs2ioda_resolved(config_dir: Path, cycle_time: str, *, refresh: bool = False):
    run = prepare_obs2ioda(config_dir, cycle_time, refresh=refresh)
    resolutions = _repair_manifest(config_dir, cycle_time)
    for item in resolutions:
        print(f"[OBS] cycle input resolved: {item.configured} -> {item.resolved}")
    return run


def run_obs2ioda_resolved(config_dir: Path, cycle_time: str, *, force: bool = False) -> Path:
    resolutions = _repair_manifest(config_dir, cycle_time)
    for item in resolutions:
        print(f"[OBS] corrected cycle input: {item.configured} -> {item.resolved}")
    return run_obs2ioda(config_dir, cycle_time, force=force)
