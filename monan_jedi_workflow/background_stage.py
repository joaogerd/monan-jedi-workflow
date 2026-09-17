"""Publish and validate the normalized background consumed by each JEDI cycle.

The campaign orchestrator should not make JEDI care whether a background came
from the one-time MPAS initialization or from the preceding cycling forecast.
This module gives both producers the same small filesystem contract:

``work/background/<cycle_id>/trajectory.nc``
    MPAS state at analysis time minus three hours for the FGAT trajectory.
``work/background/<cycle_id>/state.nc``
    Full MPAS state at analysis time used to initialize the analysis output.
``work/background/<cycle_id>/background.json``
    Provenance describing which MPAS run produced the two files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from .cycle_context import parse_cycle_time
from .mpas_stage import load_mpas_run
from .stage_config import StageConfigurationError


@dataclass(frozen=True)
class BackgroundPublication:
    directory: Path
    trajectory: Path
    state: Path
    manifest: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _safe_link(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"background source does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if target.is_symlink() and target.resolve() == source.resolve():
            return
        if target.is_symlink():
            target.unlink()
        else:
            raise FileExistsError(
                f"background publication refuses to overwrite a real file: {target}"
            )
    target.symlink_to(source.resolve())


def _background_directory(experiment_dir: Path, cycle_id: str) -> Path:
    return experiment_dir.resolve() / "work" / "background" / cycle_id


def publish_background(
    experiment_dir: Path,
    *,
    mpas_config_dir: Path,
    source_cycle_time: str,
    target_cycle_time: str,
) -> BackgroundPublication:
    """Publish the MPAS +3/+6-style products required by one JEDI cycle.

    ``target_cycle_time`` need not be exactly six hours after the MPAS start;
    it only needs to fall inside the declared MPAS integration.  This permits a
    longer operational forecast to provide the same +6 h cycling background
    without a second MPAS execution.
    """
    experiment_dir = experiment_dir.resolve()
    source_cycle = parse_cycle_time(source_cycle_time)
    target_cycle = parse_cycle_time(target_cycle_time)
    run = load_mpas_run(mpas_config_dir.resolve(), source_cycle.cycle_time)

    lead_hours = int(run.config.get("lead_hours", 0))
    valid_time = source_cycle.value + timedelta(hours=lead_hours)
    trajectory_time = target_cycle.value - timedelta(hours=3)
    if target_cycle.value <= source_cycle.value:
        raise StageConfigurationError(
            "background target cycle must be later than the MPAS source cycle"
        )
    if target_cycle.value > valid_time:
        raise StageConfigurationError(
            "background target cycle lies beyond the MPAS integration: "
            f"target={target_cycle.cycle_time}, valid={valid_time.isoformat()}"
        )
    if trajectory_time < source_cycle.value:
        raise StageConfigurationError(
            "background trajectory time lies before the MPAS integration start"
        )

    trajectory_source = run.run_dir / (
        "mpasout." + trajectory_time.strftime("%Y-%m-%d_%H.%M.%S") + ".nc"
    )
    state_source = run.run_dir / (
        "mpasout." + target_cycle.value.strftime("%Y-%m-%d_%H.%M.%S") + ".nc"
    )
    if not trajectory_source.is_file():
        raise FileNotFoundError(
            f"MPAS trajectory product for {target_cycle.cycle_time} does not exist: "
            f"{trajectory_source}"
        )
    if not state_source.is_file():
        raise FileNotFoundError(
            f"MPAS analysis-time state for {target_cycle.cycle_time} does not exist: "
            f"{state_source}"
        )

    directory = _background_directory(experiment_dir, target_cycle.cycle_id)
    trajectory = directory / "trajectory.nc"
    state = directory / "state.nc"
    manifest = directory / "background.json"
    _safe_link(trajectory_source, trajectory)
    _safe_link(state_source, state)
    _write_json(
        manifest,
        {
            "schema_version": 1,
            "source_cycle": source_cycle.cycle_time,
            "source_run_dir": str(run.run_dir),
            "target_cycle": target_cycle.cycle_time,
            "target_cycle_id": target_cycle.cycle_id,
            "trajectory_time": trajectory_time.isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            ),
            "trajectory_source": str(trajectory_source),
            "trajectory_size_bytes": trajectory_source.stat().st_size,
            "trajectory_sha256": _sha256(trajectory_source),
            "state_source": str(state_source),
            "state_size_bytes": state_source.stat().st_size,
            "state_sha256": _sha256(state_source),
        },
    )
    return BackgroundPublication(directory, trajectory, state, manifest)


def check_background(experiment_dir: Path, cycle_time: str) -> Path:
    """Validate the normalized background for ``cycle_time`` and record evidence."""
    cycle = parse_cycle_time(cycle_time)
    directory = _background_directory(experiment_dir.resolve(), cycle.cycle_id)
    trajectory = directory / "trajectory.nc"
    state = directory / "state.nc"
    missing = [str(path) for path in (trajectory, state) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "background is incomplete for " + cycle.cycle_time + ": " + ", ".join(missing)
        )

    validation = directory / "background-validation.json"
    _write_json(
        validation,
        {
            "schema_version": 1,
            "cycle_time": cycle.cycle_time,
            "cycle_id": cycle.cycle_id,
            "ready": True,
            "trajectory": str(trajectory),
            "trajectory_size_bytes": trajectory.stat().st_size,
            "state": str(state),
            "state_size_bytes": state.stat().st_size,
        },
    )
    return validation
