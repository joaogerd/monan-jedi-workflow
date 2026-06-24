"""Cycle-aware Obs2IODA conversion stage for MONAN-JEDI experiments."""

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
    render_text,
    resolve_path,
)


@dataclass(frozen=True)
class Obs2IODARun:
    cycle: CycleContext
    work_dir: Path
    manifest_path: Path
    config_dir: Path
    config: dict[str, Any]
    context: dict[str, str]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise StageConfigurationError(f"{label} must be a list.")
    return value


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StageConfigurationError(f"{label} must be a mapping.")
    return value


def load_obs2ioda_run(config_dir: Path, cycle_time: str) -> Obs2IODARun:
    """Load ``obs2ioda.yaml`` and resolve its cycle-specific work directory."""
    config_dir = config_dir.resolve()
    config = load_stage_config(config_dir, "obs2ioda.yaml", "obs2ioda")
    cycle = parse_cycle_time(cycle_time)
    context = cycle_render_context(cycle)
    work_dir_value = config.get("work_dir")
    if not isinstance(work_dir_value, str) or not work_dir_value:
        raise StageConfigurationError("obs2ioda.work_dir must be a non-empty string.")
    work_dir = resolve_path(
        work_dir_value,
        config_dir=config_dir,
        context=context,
        label="obs2ioda.work_dir",
    )
    context = {**context, "work_dir": str(work_dir)}
    return Obs2IODARun(
        cycle=cycle,
        work_dir=work_dir,
        manifest_path=work_dir / ".monan-jedi-workflow" / "obs2ioda.json",
        config_dir=config_dir,
        config=config,
        context=context,
    )


def _render_converter(run: Obs2IODARun, entry: dict[str, Any], index: int) -> dict[str, Any]:
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise StageConfigurationError(f"obs2ioda.converters[{index}].name must be a non-empty string.")
    argv = _require_list(entry.get("argv"), f"obs2ioda.converters[{index}].argv")
    if any(not isinstance(item, str) or not item for item in argv):
        raise StageConfigurationError(
            f"obs2ioda.converters[{index}].argv must contain non-empty strings."
        )
    inputs = _require_list(entry.get("inputs", []), f"obs2ioda.converters[{index}].inputs")
    outputs = _require_list(entry.get("outputs"), f"obs2ioda.converters[{index}].outputs")
    if not outputs:
        raise StageConfigurationError(f"obs2ioda.converters[{index}].outputs cannot be empty.")

    rendered_argv = [
        render_text(item, run.context, label=f"obs2ioda.converters[{index}].argv item")
        for item in argv
    ]
    rendered_inputs = [
        resolve_path(
            item,
            config_dir=run.config_dir,
            context=run.context,
            label=f"obs2ioda.converters[{index}].inputs item",
        )
        for item in inputs
    ]
    rendered_outputs = [
        resolve_path(
            item,
            config_dir=run.config_dir,
            context=run.context,
            label=f"obs2ioda.converters[{index}].outputs item",
        )
        for item in outputs
    ]
    return {
        "name": name,
        "argv": rendered_argv,
        "inputs": [str(path) for path in rendered_inputs],
        "outputs": [str(path) for path in rendered_outputs],
    }


def _load_manifest(run: Obs2IODARun) -> dict[str, Any]:
    if not run.manifest_path.exists():
        raise FileNotFoundError(
            "Obs2IODA manifest not found. Run 'obs2ioda-prepare' first: "
            f"{run.manifest_path}"
        )
    payload = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise StageConfigurationError(f"Obs2IODA manifest must be a JSON object: {run.manifest_path}")
    return payload


def _write_manifest(run: Obs2IODARun, payload: dict[str, Any]) -> None:
    run.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    run.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare_obs2ioda(config_dir: Path, cycle_time: str) -> Obs2IODARun:
    """Preflight input files and persist the conversion plan for one cycle."""
    run = load_obs2ioda_run(config_dir, cycle_time)
    run.work_dir.mkdir(parents=True, exist_ok=True)
    entries = _require_list(run.config.get("converters"), "obs2ioda.converters")
    converters = [
        _render_converter(run, _require_mapping(item, f"obs2ioda.converters[{index}]"), index)
        for index, item in enumerate(entries)
    ]
    for converter in converters:
        missing = [path for path in converter["inputs"] if not Path(path).is_file()]
        if missing:
            raise FileNotFoundError(
                f"Obs2IODA converter '{converter['name']}' input(s) missing: " + ", ".join(missing)
            )
    _write_manifest(
        run,
        {
            "schema_version": 1,
            "prepared_at": _timestamp(),
            "cycle_time": run.cycle.cycle_time,
            "cycle_id": run.cycle.cycle_id,
            "work_dir": str(run.work_dir),
            "state": "prepared",
            "converters": converters,
        },
    )
    print(f"[OK] prepared Obs2IODA cycle: {run.cycle.cycle_time}")
    return run


def run_obs2ioda(config_dir: Path, cycle_time: str, *, force: bool = False) -> Path:
    """Run configured converters, preserving per-product logs and products."""
    run = load_obs2ioda_run(config_dir, cycle_time)
    manifest = _load_manifest(run)
    converters = _require_list(manifest.get("converters"), "obs2ioda manifest converters")
    logs_dir = run.work_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    for converter in converters:
        converter = _require_mapping(converter, "obs2ioda manifest converter")
        name = converter.get("name")
        if not isinstance(name, str) or not name:
            raise StageConfigurationError("Obs2IODA manifest converter has no valid name.")
        outputs = [Path(value) for value in _require_list(converter.get("outputs"), f"{name}.outputs")]
        complete = all(path.is_file() and path.stat().st_size > 0 for path in outputs)
        if complete and not force:
            print(f"[SKIP] Obs2IODA converter already produced outputs: {name}")
            continue

        for output in outputs:
            output.parent.mkdir(parents=True, exist_ok=True)
        stdout_path = logs_dir / f"{name}.stdout.log"
        stderr_path = logs_dir / f"{name}.stderr.log"
        process = subprocess.run(
            _require_list(converter.get("argv"), f"{name}.argv"),
            cwd=run.work_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_path.write_text(process.stdout, encoding="utf-8")
        stderr_path.write_text(process.stderr, encoding="utf-8")
        if process.returncode != 0:
            manifest.update({"state": "failed", "failed_converter": name})
            _write_manifest(run, manifest)
            raise RuntimeError(
                f"Obs2IODA converter '{name}' failed with return code {process.returncode}. "
                f"See {stdout_path} and {stderr_path}."
            )
        missing = [str(path) for path in outputs if not path.is_file() or path.stat().st_size == 0]
        if missing:
            manifest.update({"state": "invalid-output", "failed_converter": name})
            _write_manifest(run, manifest)
            raise RuntimeError(
                f"Obs2IODA converter '{name}' did not create required output(s): "
                + ", ".join(missing)
            )
        print(f"[OK] Obs2IODA converter: {name}")

    manifest.update({"state": "success", "finished_at": _timestamp()})
    _write_manifest(run, manifest)
    print(f"[OK] completed Obs2IODA cycle: {run.cycle.cycle_time}")
    return run.manifest_path
