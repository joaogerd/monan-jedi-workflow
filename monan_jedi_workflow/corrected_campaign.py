"""Generate and materialize a clean multi-day corrected cycling campaign.

The validated 2018-04-15 corrected replay remains the scientific starting
point.  This module extends that same contract over an arbitrary 6-hourly end
cycle while keeping every cycle in one simpleWorkflow execution graph so that
cross-cycle dependencies and restart semantics remain explicit.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from .corrected_replay import (
    _FIRST_CYCLE,
    _INITIAL_PREVIOUS_ID,
    _copy_clean_case,
    _initial_inputs,
    _patch_jedi,
    _patch_mpas,
    _patch_obs,
    _safe_initial_link,
)
from .stage_config import StageConfigurationError

_CYCLE_STEP = timedelta(hours=6)


def _parse_cycle(value: str) -> datetime:
    try:
        cycle = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StageConfigurationError(f"invalid campaign cycle time: {value}") from exc
    if cycle.tzinfo is None:
        cycle = cycle.replace(tzinfo=timezone.utc)
    cycle = cycle.astimezone(timezone.utc)
    if cycle.minute or cycle.second or cycle.microsecond or cycle.hour not in {0, 6, 12, 18}:
        raise StageConfigurationError(
            "corrected campaign cycles must be aligned to 00/06/12/18Z"
        )
    return cycle


def _iso(cycle: datetime) -> str:
    return cycle.strftime("%Y-%m-%dT%H:%M:%SZ")


def _cycle_id(cycle: datetime) -> str:
    return cycle.strftime("%Y%m%dT%H%M%SZ")


def _cycle_key(cycle: datetime) -> str:
    return cycle.strftime("%Y%m%d%H")


def _obs_id(cycle: datetime) -> str:
    return cycle.strftime("%Y%m%d%H")


def _mpas_file_time(cycle: datetime) -> str:
    return cycle.strftime("%Y-%m-%d_%H.00.00")


def _cycles(start_cycle: str, end_cycle: str) -> list[datetime]:
    start = _parse_cycle(start_cycle)
    end = _parse_cycle(end_cycle)
    validated_start = _parse_cycle(_FIRST_CYCLE)
    if start != validated_start:
        raise StageConfigurationError(
            "the corrected campaign currently requires the validated first cycle "
            f"{_FIRST_CYCLE}; found {start_cycle}"
        )
    if end < start:
        raise StageConfigurationError("campaign end cycle precedes the first cycle")
    span = end - start
    if span % _CYCLE_STEP:
        raise StageConfigurationError("campaign duration must be a multiple of 6 hours")
    count = int(span / _CYCLE_STEP) + 1
    return [start + index * _CYCLE_STEP for index in range(count)]


def _validation_gate(name: str, dependency: str, validation: str) -> dict[str, Any]:
    return {
        "name": name,
        "depends_on": [dependency],
        "argv": ["monan-jedi-workflow", "validation-gate", validation],
        "input_fingerprint": "sha256",
        "inputs": {"required": [validation]},
    }


def _jedi_tasks(
    cycle: datetime,
    *,
    first: bool,
    previous_cycle: datetime | None,
) -> list[dict[str, Any]]:
    key = _cycle_key(cycle)
    run_id = _cycle_id(cycle)
    cycle_iso = _iso(cycle)
    analysis_file_time = _mpas_file_time(cycle)
    prefix = f"jedi{key}"

    prepare: dict[str, Any] = {
        "name": f"{prefix}_prepare",
        "argv": [
            "monan-jedi-workflow",
            "jedi-prepare",
            "{experiment_dir}",
            "--cycle",
            cycle_iso,
        ],
        "inputs": {"required": ["{experiment_dir}/jedi.yaml"]},
        "outputs": {
            "required": [
                f"{{experiment_dir}}/work/jedi/{run_id}/run_jedi.pbs",
                f"{{experiment_dir}}/work/jedi/{run_id}/.monan-jedi-workflow/jedi-submission.json",
            ]
        },
    }

    if not first:
        if previous_cycle is None:
            raise AssertionError("non-first JEDI cycle requires a previous cycle")
        previous_key = _cycle_key(previous_cycle)
        previous_run_id = _cycle_id(previous_cycle)
        trajectory_time = _mpas_file_time(cycle - timedelta(hours=3))
        obs_id = _obs_id(cycle)
        prepare["depends_on"] = [f"mpas{previous_key}_gate", f"obs{key}_gate"]
        prepare["inputs"]["required"].extend(
            [
                f"{{experiment_dir}}/work/mpas/{previous_run_id}/mpasout.{trajectory_time}.nc",
                f"{{experiment_dir}}/work/mpas/{previous_run_id}/mpasout.{analysis_file_time}.nc",
                f"{{experiment_dir}}/work/obs/{obs_id}/sondes_obs_{obs_id}.h5",
                f"{{experiment_dir}}/work/obs/{obs_id}/sfc_obs_{obs_id}.h5",
                f"{{experiment_dir}}/work/obs/{obs_id}/gnssro_obs_{obs_id}.h5",
            ]
        )

    submission = f"{{experiment_dir}}/work/jedi/{run_id}/.monan-jedi-workflow/jedi-submission.json"
    validation = f"{{experiment_dir}}/work/jedi/{run_id}/.monan-jedi-workflow/jedi-validation.json"
    artifacts = f"{{experiment_dir}}/work/jedi/{run_id}/.monan-jedi-workflow/jedi-artifacts.json"
    analysis = f"{{experiment_dir}}/work/jedi/{run_id}/Data/states/mpas.3dvar.{analysis_file_time}.nc"

    tasks: list[dict[str, Any]] = [prepare]
    tasks.append(
        {
            "name": f"{prefix}_submit",
            "depends_on": [f"{prefix}_prepare"],
            "argv": [
                "monan-jedi-workflow",
                "jedi-submit",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "outputs": {"required": [submission]},
        }
    )
    tasks.append(
        {
            "name": f"{prefix}_wait",
            "depends_on": [f"{prefix}_submit"],
            "argv": [
                "monan-jedi-workflow",
                "jedi-wait",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
                "--poll-seconds",
                "30",
            ],
            "outputs": {"required": [submission]},
        }
    )
    tasks.append(
        {
            "name": f"{prefix}_validate",
            "depends_on": [f"{prefix}_wait"],
            "argv": [
                "monan-jedi-workflow",
                "jedi-validate",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "outputs": {"required": [validation, artifacts, analysis]},
        }
    )
    tasks.append(_validation_gate(f"{prefix}_gate", f"{prefix}_validate", validation))
    return tasks


def _mpas_tasks(cycle: datetime) -> list[dict[str, Any]]:
    key = _cycle_key(cycle)
    run_id = _cycle_id(cycle)
    cycle_iso = _iso(cycle)
    prefix = f"mpas{key}"
    analysis_time = _mpas_file_time(cycle)
    plus3 = _mpas_file_time(cycle + timedelta(hours=3))
    plus6 = _mpas_file_time(cycle + timedelta(hours=6))
    submission = f"{{experiment_dir}}/work/mpas/{run_id}/.monan-jedi-workflow/mpas-submission.json"
    validation = f"{{experiment_dir}}/work/mpas/{run_id}/.monan-jedi-workflow/mpas-validation.json"

    return [
        {
            "name": f"{prefix}_prepare",
            "depends_on": [f"jedi{key}_gate"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-prepare",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "inputs": {
                "required": [
                    "{experiment_dir}/mpas.yaml",
                    f"{{experiment_dir}}/work/jedi/{run_id}/Data/states/mpas.3dvar.{analysis_time}.nc",
                ]
            },
            "outputs": {
                "required": [
                    f"{{experiment_dir}}/work/mpas/{run_id}/run_mpas.pbs",
                    submission,
                ]
            },
        },
        {
            "name": f"{prefix}_submit",
            "depends_on": [f"{prefix}_prepare"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-submit",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "outputs": {"required": [submission]},
        },
        {
            "name": f"{prefix}_wait",
            "depends_on": [f"{prefix}_submit"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-wait",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
                "--poll-seconds",
                "30",
            ],
            "outputs": {"required": [submission]},
        },
        {
            "name": f"{prefix}_validate",
            "depends_on": [f"{prefix}_wait"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-validate",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "outputs": {
                "required": [
                    validation,
                    f"{{experiment_dir}}/work/mpas/{run_id}/mpasout.{plus3}.nc",
                    f"{{experiment_dir}}/work/mpas/{run_id}/mpasout.{plus6}.nc",
                ]
            },
        },
        _validation_gate(f"{prefix}_gate", f"{prefix}_validate", validation),
    ]


def _obs_tasks(cycle: datetime, previous_cycle: datetime) -> list[dict[str, Any]]:
    key = _cycle_key(cycle)
    previous_key = _cycle_key(previous_cycle)
    cycle_iso = _iso(cycle)
    obs_id = _obs_id(cycle)
    prefix = f"obs{key}"
    doctor = f"{{experiment_dir}}/work/obs/{obs_id}/.monan-jedi-workflow/obs2ioda-doctor.json"
    prepared = f"{{experiment_dir}}/work/obs/{obs_id}/.monan-jedi-workflow/obs2ioda.json"
    validation = f"{{experiment_dir}}/work/obs/{obs_id}/.monan-jedi-workflow/obs2ioda-validation.json"
    sondes = f"{{experiment_dir}}/work/obs/{obs_id}/sondes_obs_{obs_id}.h5"
    sfc = f"{{experiment_dir}}/work/obs/{obs_id}/sfc_obs_{obs_id}.h5"
    gnssro = f"{{experiment_dir}}/work/obs/{obs_id}/gnssro_obs_{obs_id}.h5"

    return [
        {
            "name": f"{prefix}_doctor",
            "depends_on": [f"jedi{previous_key}_gate"],
            "argv": [
                "monan-jedi-workflow",
                "obs2ioda-doctor",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "inputs": {"required": ["{experiment_dir}/obs2ioda.yaml"]},
            "outputs": {"required": [doctor]},
        },
        {
            "name": f"{prefix}_prepare",
            "depends_on": [f"{prefix}_doctor"],
            "argv": [
                "monan-jedi-workflow",
                "obs2ioda-prepare",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "outputs": {"required": [prepared]},
        },
        {
            "name": f"{prefix}_run",
            "depends_on": [f"{prefix}_prepare"],
            "argv": [
                "monan-jedi-workflow",
                "obs2ioda-run",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "outputs": {"required": [sondes, sfc, gnssro]},
        },
        {
            "name": f"{prefix}_validate",
            "depends_on": [f"{prefix}_run"],
            "argv": [
                "monan-jedi-workflow",
                "obs2ioda-validate",
                "{experiment_dir}",
                "--cycle",
                cycle_iso,
            ],
            "outputs": {"required": [validation, sondes, sfc, gnssro]},
        },
        _validation_gate(f"{prefix}_gate", f"{prefix}_validate", validation),
    ]


def build_corrected_campaign_workflow(
    *,
    start_cycle: str = _FIRST_CYCLE,
    end_cycle: str,
    experiment_dir: str,
) -> dict[str, Any]:
    """Build one explicit dependency graph for a corrected cycling campaign."""
    cycles = _cycles(start_cycle, end_cycle)
    tasks: list[dict[str, Any]] = []

    for index, cycle in enumerate(cycles):
        previous = cycles[index - 1] if index else None
        tasks.extend(_jedi_tasks(cycle, first=index == 0, previous_cycle=previous))
        if index + 1 < len(cycles):
            next_cycle = cycles[index + 1]
            tasks.extend(_mpas_tasks(cycle))
            tasks.extend(_obs_tasks(next_cycle, cycle))

    start_key = _cycle_key(cycles[0])
    end_key = _cycle_key(cycles[-1])
    return {
        "workflow": {"name": f"monan_jedi_corrected_campaign_{start_key}_{end_key}"},
        "context": {"experiment_dir": experiment_dir},
        "tasks": tasks,
    }


def materialize_corrected_campaign(
    *,
    initial_jedi_case: Path,
    cycling_jedi_case: Path,
    mpas_case: Path,
    obs2ioda_config: Path,
    destination: Path,
    start_cycle: str = _FIRST_CYCLE,
    end_cycle: str,
) -> Path:
    """Create a clean, non-executed corrected campaign through ``end_cycle``."""
    cycles = _cycles(start_cycle, end_cycle)
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"campaign destination already exists: {destination}")

    inputs = _initial_inputs(initial_jedi_case.resolve())

    try:
        _copy_clean_case(cycling_jedi_case.resolve(), destination)
        campaign_root = destination / "work"
        _patch_jedi(destination, campaign_root)
        _patch_mpas(mpas_case.resolve(), destination, campaign_root)
        _patch_obs(obs2ioda_config.resolve(), destination, campaign_root)

        workflow = build_corrected_campaign_workflow(
            start_cycle=start_cycle,
            end_cycle=end_cycle,
            experiment_dir=str(destination),
        )
        (destination / "workflow.yaml").write_text(
            yaml.safe_dump(workflow, sort_keys=False), encoding="utf-8"
        )
        (destination / "campaign.yaml").write_text(
            yaml.safe_dump(
                {
                    "campaign": {
                        "start_cycle": _iso(cycles[0]),
                        "end_cycle": _iso(cycles[-1]),
                        "cycle_interval_hours": 6,
                        "analysis_cycles": len(cycles),
                        "forecast_legs": len(cycles) - 1,
                        "duration_hours": int((cycles[-1] - cycles[0]).total_seconds() // 3600),
                    }
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        initial_mpas = campaign_root / "mpas" / _INITIAL_PREVIOUS_ID
        _safe_initial_link(
            inputs["trajectory"],
            initial_mpas / "mpasout.2018-04-14_21.00.00.nc",
        )
        _safe_initial_link(
            inputs["analysis_base"],
            initial_mpas / "mpasout.2018-04-15_00.00.00.nc",
        )
        initial_obs = campaign_root / "obs" / "2018041500"
        _safe_initial_link(inputs["sondes"], initial_obs / "sondes_obs_2018041500.h5")
        _safe_initial_link(inputs["sfc"], initial_obs / "sfc_obs_2018041500.h5")
        _safe_initial_link(inputs["gnssro"], initial_obs / "gnssro_obs_2018041500.h5")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return destination
