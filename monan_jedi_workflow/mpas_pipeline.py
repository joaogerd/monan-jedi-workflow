"""High-level, Python-first MPAS workflow planning and state management.

This module owns configuration validation, input/static provenance, stage
selection and idempotent state. Domain executors (WPS, MPAS init, MPAS,
Obs2IODA and future MPAS-JEDI) remain separate adapters.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .cycle_context import CycleContext, parse_cycle_time
from .stage_config import StageConfigurationError, render_text
from .yaml_utils import load_yaml_file


class MPASPipelineError(RuntimeError):
    """Raised when a high-level MPAS workflow contract is invalid."""


@dataclass(frozen=True)
class InputAsset:
    name: str
    provider: str
    path: Path
    url: str | None
    required: bool


@dataclass(frozen=True)
class StagePlan:
    name: str
    depends_on: tuple[str, ...]
    enabled: bool
    reason: str


@dataclass(frozen=True)
class PipelineRun:
    config_path: Path
    config_dir: Path
    cycle: CycleContext
    config: dict[str, Any]
    context: dict[str, str]
    work_root: Path
    state_root: Path


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MPASPipelineError(f"{label} must be a mapping.")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise MPASPipelineError(f"{label} must be a list.")
    return value


def _bool_or_auto(value: Any, label: str) -> bool | str:
    if isinstance(value, bool):
        return value
    if value == "auto":
        return value
    raise MPASPipelineError(f"{label} must be true, false, or 'auto'.")


def _render_path(value: str, run: PipelineRun, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise MPASPipelineError(f"{label} must be a non-empty string.")
    rendered = Path(render_text(value, run.context, label=label))
    return rendered if rendered.is_absolute() else run.config_dir / rendered


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fingerprint_file(path: Path, *, checksum: bool) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    record: dict[str, Any] = {
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_at_ns": stat.st_mtime_ns,
    }
    if checksum:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        record["sha256"] = digest.hexdigest()
    return record


def load_pipeline_run(config_path: str | Path, cycle_time: str) -> PipelineRun:
    """Load high-level YAML and resolve one reproducible cycle context."""
    path = Path(config_path).resolve()
    data = load_yaml_file(path)
    pipeline = _mapping(data.get("pipeline"), "pipeline")
    cycle = parse_cycle_time(cycle_time)
    context = cycle.render_context(lead_hours=int(pipeline.get("forecast_hours", 0)))
    context["config_dir"] = str(path.parent)
    work_root = _render_path(str(pipeline.get("work_root", "work")), PipelineRun(path, path.parent, cycle, pipeline, context, path.parent, path.parent), "pipeline.work_root")
    context["work_root"] = str(work_root)
    return PipelineRun(path, path.parent, cycle, pipeline, context, work_root, work_root / ".monan-jedi-mpas" / "state")


def resolve_inputs(run: PipelineRun) -> list[InputAsset]:
    """Resolve configured meteorological input sources without downloading them."""
    sources = _mapping(run.config.get("inputs", {}), "pipeline.inputs")
    assets: list[InputAsset] = []
    for index, raw in enumerate(_list(sources.get("assets", []), "pipeline.inputs.assets")):
        item = _mapping(raw, f"pipeline.inputs.assets[{index}]")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise MPASPipelineError(f"pipeline.inputs.assets[{index}].name must be a non-empty string.")
        provider = item.get("provider", "local")
        if provider not in {"local", "infrastructure", "gfs_http", "reanalysis_http", "http"}:
            raise MPASPipelineError(f"Unsupported input provider for {name!r}: {provider!r}")
        path = _render_path(str(item.get("path", "")), run, f"pipeline.inputs.assets[{index}].path")
        url = item.get("url")
        if provider in {"gfs_http", "reanalysis_http", "http"}:
            if not isinstance(url, str) or not url:
                raise MPASPipelineError(f"Remote input {name!r} requires a non-empty url.")
            url = render_text(url, run.context, label=f"pipeline.inputs.assets[{index}].url")
        assets.append(InputAsset(name, provider, path, url, bool(item.get("required", True))))
    return assets


def resolve_static_assets(run: PipelineRun) -> list[tuple[str, Path]]:
    static = _mapping(run.config.get("static", {}), "pipeline.static")
    items = _mapping(static.get("assets", {}), "pipeline.static.assets")
    result: list[tuple[str, Path]] = []
    for name, value in items.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise MPASPipelineError("pipeline.static.assets must map names to path strings.")
        result.append((name, _render_path(value, run, f"pipeline.static.assets.{name}")))
    return result


def should_use_wps(run: PipelineRun) -> bool:
    stages = _mapping(run.config.get("stages", {}), "pipeline.stages")
    setting = _bool_or_auto(stages.get("wps", "auto"), "pipeline.stages.wps")
    if isinstance(setting, bool):
        return setting
    return any(asset.provider in {"gfs_http", "reanalysis_http", "http"} for asset in resolve_inputs(run))


def build_plan(run: PipelineRun) -> list[StagePlan]:
    """Build the dependency graph selected by a high-level experiment YAML."""
    stages = _mapping(run.config.get("stages", {}), "pipeline.stages")
    mode = stages.get("mode", "forecast")
    if mode not in {"prepare", "forecast", "cycle", "bmatrix"}:
        raise MPASPipelineError("pipeline.stages.mode must be prepare, forecast, cycle, or bmatrix.")
    plans = [
        StagePlan("inputs", (), True, "validate or acquire declared meteorological inputs"),
        StagePlan("static", ("inputs",), True, "validate fixed mesh, graph, physics and invariant assets"),
    ]
    previous = "static"
    if should_use_wps(run):
        plans.append(StagePlan("wps", (previous,), True, "input format requires WPS/UNGRIB"))
        previous = "wps"
    else:
        plans.append(StagePlan("wps", (previous,), False, "input declared as directly usable by MPAS init"))
    if mode != "prepare":
        plans.append(StagePlan("mpas_init", (previous,), True, "create or reuse MPAS initial condition"))
        plans.append(StagePlan("mpas_forecast", ("mpas_init",), True, "create or reuse MPAS forecast states"))
    if mode == "cycle":
        plans.append(StagePlan("observations", ("inputs",), True, "convert configured observations to IODA"))
        plans.append(StagePlan("assimilation", ("mpas_forecast", "observations"), True, "prepare cycle-aware MPAS-JEDI analysis"))
    if mode == "bmatrix":
        plans.append(StagePlan("bmatrix_samples", ("mpas_forecast",), True, "publish forecast-state contract for B-matrix samples"))
    return plans


def validate_contract(run: PipelineRun, *, strict_inputs: bool = True) -> dict[str, Any]:
    """Validate configuration, source declarations and static assets without execution."""
    inputs = resolve_inputs(run)
    static = resolve_static_assets(run)
    missing_inputs = [asset.name for asset in inputs if asset.required and asset.provider in {"local", "infrastructure"} and not asset.path.is_file()]
    missing_static = [name for name, path in static if not path.exists()]
    plan = build_plan(run)
    report = {
        "schema_version": 1,
        "validated_at": _timestamp(),
        "config": str(run.config_path),
        "cycle_time": run.cycle.cycle_time,
        "inputs": [
            {"name": asset.name, "provider": asset.provider, "path": str(asset.path), "url": asset.url, "exists": asset.path.is_file()}
            for asset in inputs
        ],
        "static": [{"name": name, "path": str(path), "exists": path.exists()} for name, path in static],
        "plan": [plan.__dict__ for plan in plan],
        "missing_inputs": missing_inputs,
        "missing_static": missing_static,
        "valid": not missing_static and (not strict_inputs or not missing_inputs),
    }
    if not report["valid"]:
        details = []
        if missing_inputs:
            details.append("missing local input(s): " + ", ".join(missing_inputs))
        if missing_static:
            details.append("missing static asset(s): " + ", ".join(missing_static))
        raise MPASPipelineError("MPAS workflow validation failed: " + "; ".join(details))
    return report


def state_path(run: PipelineRun, stage: str) -> Path:
    return run.state_root / run.cycle.cycle_id / f"{stage}.json"


def write_state(run: PipelineRun, stage: str, *, inputs: list[Path], outputs: list[Path], action: str, checksum: bool = False) -> Path:
    """Write an atomic, content-addressed stage record for reuse decisions."""
    payload = {
        "schema_version": 1,
        "recorded_at": _timestamp(),
        "stage": stage,
        "cycle_time": run.cycle.cycle_time,
        "config_sha256": _sha256_bytes(json.dumps(run.config, sort_keys=True).encode("utf-8")),
        "action": action,
        "inputs": [_fingerprint_file(path, checksum=checksum) for path in inputs],
        "outputs": [_fingerprint_file(path, checksum=checksum) for path in outputs],
    }
    target = state_path(run, stage)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def reusable_state(run: PipelineRun, stage: str) -> bool:
    """Return true only when recorded outputs still exist and are non-empty."""
    path = state_path(run, stage)
    if not path.is_file():
        return False
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if record.get("config_sha256") != _sha256_bytes(json.dumps(run.config, sort_keys=True).encode("utf-8")):
        return False
    outputs = record.get("outputs", [])
    return bool(outputs) and all(item.get("exists") and int(item.get("size_bytes", 0)) > 0 and Path(item["path"]).is_file() for item in outputs)


def acquire_remote(asset: InputAsset, *, allow_download: bool, force: bool = False) -> Path:
    """Download a declared remote asset only when explicitly permitted."""
    if asset.provider in {"local", "infrastructure"}:
        return asset.path
    if asset.path.is_file() and asset.path.stat().st_size > 0 and not force:
        return asset.path
    if not allow_download:
        raise MPASPipelineError(
            f"Input {asset.name!r} is remote and unavailable locally. Re-run with explicit download permission."
        )
    assert asset.url is not None
    asset.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = asset.path.with_suffix(asset.path.suffix + ".part")
    with urlopen(asset.url, timeout=60) as response, temporary.open("wb") as stream:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            stream.write(block)
    if temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise MPASPipelineError(f"Downloaded zero-byte input for {asset.name!r}.")
    temporary.replace(asset.path)
    return asset.path
