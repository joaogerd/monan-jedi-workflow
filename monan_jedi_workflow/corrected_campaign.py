"""Generate and materialize compact corrected cycling campaigns.

The campaign YAML defines the requested period.  The generated workflow defines
one one-time MPAS initialization and one static set of cycle tasks.  Native
simpleWorkflow cycle expansion supplies the timestamps at runtime, so the YAML
does not grow with the number of analysis times.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from .case_utils import (
    absolutize_case_path,
    copy_clean_case,
    load_yaml,
    write_yaml,
)
from .stage_config import StageConfigurationError

def _parse_cycle(value: str) -> datetime:
    try:
        cycle = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StageConfigurationError(f"invalid campaign cycle time: {value}") from exc
    if cycle.tzinfo is None:
        cycle = cycle.replace(tzinfo=timezone.utc)
    cycle = cycle.astimezone(timezone.utc)
    return cycle


def _iso(cycle: datetime) -> str:
    return cycle.strftime("%Y-%m-%dT%H:%M:%SZ")


def _cycle_id(cycle: datetime) -> str:
    return cycle.strftime("%Y%m%dT%H%M%SZ")


def _cycles(
    start_cycle: str, end_cycle: str, cycle_interval_hours: int = 6
) -> list[datetime]:
    """Return the inclusive campaign cycle range using the declared interval."""
    if cycle_interval_hours <= 0:
        raise StageConfigurationError("cycle_interval_hours must be positive")
    step = timedelta(hours=cycle_interval_hours)
    start = _parse_cycle(start_cycle)
    end = _parse_cycle(end_cycle)
    if end < start:
        raise StageConfigurationError("campaign end cycle precedes the first cycle")
    span = end - start
    if span % step:
        raise StageConfigurationError(
            "campaign duration must be a multiple of cycle_interval_hours"
        )
    count = int(span / step) + 1
    return [start + index * step for index in range(count)]


def _validation_gate(
    name: str,
    dependency: str,
    validation: str,
    *,
    cycle_scope: str | None = None,
) -> dict[str, Any]:
    task: dict[str, Any] = {
        "name": name,
        "depends_on": [dependency],
        "argv": ["monan-jedi-workflow", "validation-gate", validation],
        "input_fingerprint": "sha256",
        "inputs": {"required": [validation]},
    }
    if cycle_scope is not None:
        task["cycle_scope"] = cycle_scope
    return task


def _initialization_tasks(
    start_cycle: datetime, cycle_interval_hours: int
) -> list[dict[str, Any]]:
    source_cycle = start_cycle - timedelta(hours=cycle_interval_hours)
    source_iso = _iso(source_cycle)
    source_id = _cycle_id(source_cycle)
    target_iso = _iso(start_cycle)
    target_id = _cycle_id(start_cycle)
    root = "{experiment_dir}"
    run = f"{root}/work/initialization/mpas/{source_id}"
    submission = f"{run}/.monan-jedi-workflow/mpas-submission.json"
    validation = f"{run}/.monan-jedi-workflow/mpas-validation.json"
    background = f"{root}/work/background/{target_id}"

    return [
        {
            "name": "mpas_initial_prepare",
            "argv": [
                "monan-jedi-workflow",
                "mpas-prepare",
                f"{root}/initialization",
                "--cycle",
                source_iso,
            ],
            "inputs": {"required": [f"{root}/initialization/mpas.yaml"]},
            "outputs": {
                "required": [
                    f"{run}/run_mpas.pbs",
                    submission,
                ]
            },
        },
        {
            "name": "mpas_initial_submit",
            "depends_on": ["mpas_initial_prepare"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-submit",
                f"{root}/initialization",
                "--cycle",
                source_iso,
            ],
            "outputs": {"required": [submission]},
        },
        {
            "name": "mpas_initial_wait",
            "depends_on": ["mpas_initial_submit"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-wait",
                f"{root}/initialization",
                "--cycle",
                source_iso,
                "--poll-seconds",
                "30",
            ],
            "outputs": {"required": [submission]},
        },
        {
            "name": "mpas_initial_validate",
            "depends_on": ["mpas_initial_wait"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-validate",
                f"{root}/initialization",
                "--cycle",
                source_iso,
            ],
            "outputs": {"required": [validation]},
        },
        _validation_gate("mpas_initial_gate", "mpas_initial_validate", validation),
        {
            "name": "initial_background",
            "depends_on": ["mpas_initial_gate"],
            "argv": [
                "monan-jedi-workflow",
                "background-publish",
                root,
                "--mpas-config-dir",
                f"{root}/initialization",
                "--source-cycle",
                source_iso,
                "--target-cycle",
                target_iso,
            ],
            "inputs": {"required": [validation]},
            "outputs": {
                "required": [
                    f"{background}/trajectory.nc",
                    f"{background}/state.nc",
                    f"{background}/background.json",
                ]
            },
        },
    ]


def _cycle_tasks(
    *,
    run_mpas_on_last_cycle: bool,
    observation_outputs: list[str],
    analysis_output: str,
) -> list[dict[str, Any]]:
    root = "{experiment_dir}"
    cycle_id = "{cycle_id}"
    obs_id = "{cycle_yyyymmddhh}"

    background_dir = f"{root}/work/background/{cycle_id}"
    background_validation = f"{background_dir}/background-validation.json"
    obs_dir = f"{root}/work/obs/{obs_id}"
    obs_doctor = f"{obs_dir}/.monan-jedi-workflow/obs2ioda-doctor.json"
    obs_plan = f"{obs_dir}/.monan-jedi-workflow/obs2ioda.json"
    obs_validation = f"{obs_dir}/.monan-jedi-workflow/obs2ioda-validation.json"
    if not observation_outputs:
        raise StageConfigurationError(
            "campaign requires at least one observation output declared by Obs2IODA"
        )
    obs_products = observation_outputs
    obs_files = [
        item if item.startswith("/") else f"{obs_dir}/{item}"
        for item in obs_products
    ]

    jedi_run = f"{root}/work/jedi/{cycle_id}"
    jedi_submission = f"{jedi_run}/.monan-jedi-workflow/jedi-submission.json"
    jedi_validation = f"{jedi_run}/.monan-jedi-workflow/jedi-validation.json"
    jedi_artifacts = f"{jedi_run}/.monan-jedi-workflow/jedi-artifacts.json"
    analysis = (
        analysis_output
        if analysis_output.startswith("/")
        else f"{jedi_run}/{analysis_output}"
    )

    mpas_run = f"{root}/work/mpas/{cycle_id}"
    mpas_submission = f"{mpas_run}/.monan-jedi-workflow/mpas-submission.json"
    mpas_validation = f"{mpas_run}/.monan-jedi-workflow/mpas-validation.json"
    mpas_scope = "all" if run_mpas_on_last_cycle else "not_last"

    tasks: list[dict[str, Any]] = [
        {
            "name": "background_check",
            "argv": [
                "monan-jedi-workflow",
                "background-check",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "inputs": {
                "required": [
                    f"{background_dir}/trajectory.nc",
                    f"{background_dir}/state.nc",
                ]
            },
            "outputs": {"required": [background_validation]},
        },
        {
            "name": "observations_doctor",
            "cycle_scope": "all",
            "argv": [
                "monan-jedi-workflow",
                "obs2ioda-doctor",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "inputs": {"required": [f"{root}/obs2ioda.yaml"]},
            "outputs": {"required": [obs_doctor]},
        },
        {
            "name": "observations_prepare",
            "cycle_scope": "all",
            "depends_on": ["observations_doctor"],
            "argv": [
                "monan-jedi-workflow",
                "obs2ioda-prepare",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "outputs": {"required": [obs_plan]},
        },
        {
            "name": "observations_run",
            "cycle_scope": "all",
            "depends_on": ["observations_prepare"],
            "argv": [
                "monan-jedi-workflow",
                "obs2ioda-run",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "outputs": {"required": obs_files},
        },
        {
            "name": "observations_validate",
            "cycle_scope": "all",
            "depends_on": ["observations_run"],
            "argv": [
                "monan-jedi-workflow",
                "obs2ioda-validate",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "outputs": {"required": [obs_validation, *obs_files]},
        },
        _validation_gate(
            "observations_gate", "observations_validate", obs_validation, cycle_scope="all"
        ),
        {
            "name": "jedi_prepare",
            "depends_on": ["background_check", "observations_gate"],
            "argv": [
                "monan-jedi-workflow",
                "jedi-prepare",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "inputs": {
                "required": [
                    f"{root}/jedi.yaml",
                    f"{background_dir}/trajectory.nc",
                    f"{background_dir}/state.nc",
                    *obs_files,
                ]
            },
            "outputs": {
                "required": [f"{jedi_run}/run_jedi.pbs", jedi_submission]
            },
        },
        {
            "name": "jedi_submit",
            "depends_on": ["jedi_prepare"],
            "argv": [
                "monan-jedi-workflow",
                "jedi-submit",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "outputs": {"required": [jedi_submission]},
        },
        {
            "name": "jedi_wait",
            "depends_on": ["jedi_submit"],
            "argv": [
                "monan-jedi-workflow",
                "jedi-wait",
                root,
                "--cycle",
                "{cycle_time}",
                "--poll-seconds",
                "30",
            ],
            "outputs": {"required": [jedi_submission]},
        },
        {
            "name": "jedi_validate",
            "depends_on": ["jedi_wait"],
            "argv": [
                "monan-jedi-workflow",
                "jedi-validate",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "outputs": {"required": [jedi_validation, jedi_artifacts, analysis]},
        },
        _validation_gate("jedi_gate", "jedi_validate", jedi_validation),
    ]

    for task in (
        {
            "name": "mpas_prepare",
            "cycle_scope": mpas_scope,
            "depends_on": ["jedi_gate"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-prepare",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "inputs": {"required": [f"{root}/mpas.yaml", analysis]},
            "outputs": {"required": [f"{mpas_run}/run_mpas.pbs", mpas_submission]},
        },
        {
            "name": "mpas_submit",
            "cycle_scope": mpas_scope,
            "depends_on": ["mpas_prepare"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-submit",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "outputs": {"required": [mpas_submission]},
        },
        {
            "name": "mpas_wait",
            "cycle_scope": mpas_scope,
            "depends_on": ["mpas_submit"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-wait",
                root,
                "--cycle",
                "{cycle_time}",
                "--poll-seconds",
                "30",
            ],
            "outputs": {"required": [mpas_submission]},
        },
        {
            "name": "mpas_validate",
            "cycle_scope": mpas_scope,
            "depends_on": ["mpas_wait"],
            "argv": [
                "monan-jedi-workflow",
                "mpas-validate",
                root,
                "--cycle",
                "{cycle_time}",
            ],
            "outputs": {"required": [mpas_validation]},
        },
        _validation_gate(
            "mpas_gate", "mpas_validate", mpas_validation, cycle_scope=mpas_scope
        ),
        {
            "name": "next_background",
            "cycle_scope": "not_last",
            "depends_on": ["mpas_gate"],
            "argv": [
                "monan-jedi-workflow",
                "background-publish",
                root,
                "--source-cycle",
                "{cycle_time}",
                "--target-cycle",
                "{next_cycle_time}",
            ],
            "inputs": {"required": [mpas_validation]},
            "outputs": {
                "required": [
                    f"{root}/work/background/{{next_cycle_id}}/trajectory.nc",
                    f"{root}/work/background/{{next_cycle_id}}/state.nc",
                    f"{root}/work/background/{{next_cycle_id}}/background.json",
                ]
            },
        },
    ):
        tasks.append(task)
    return tasks


def build_corrected_campaign_workflow(
    *,
    start_cycle: str = None,
    end_cycle: str,
    experiment_dir: str,
    run_mpas_on_last_cycle: bool = False,
    cycle_interval_hours: int = 6,
    observation_outputs: list[str],
    analysis_output: str,
) -> dict[str, Any]:
    """Build a constant-size native-cycle workflow for a corrected campaign."""
    cycles = _cycles(start_cycle, end_cycle, cycle_interval_hours)
    return {
        "format_version": 1,
        "workflow": {"name": "monan_jedi_corrected_campaign"},
        "context": {"experiment_dir": experiment_dir},
        "initialization": {"tasks": _initialization_tasks(cycles[0], cycle_interval_hours)},
        "cycle": {
            "start": _iso(cycles[0]),
            "end": _iso(cycles[-1]),
            "step": f"PT{cycle_interval_hours}H",
        },
        "tasks": _cycle_tasks(
            run_mpas_on_last_cycle=run_mpas_on_last_cycle,
            observation_outputs=observation_outputs,
            analysis_output=analysis_output,
        ),
    }


def _validate_cycling_contract(mpas: dict[str, Any]) -> None:
    """Validate internal consistency without imposing one scientific case."""
    lead_hours = int(mpas.get("lead_hours", -1))
    if lead_hours <= 0:
        raise StageConfigurationError("mpas.lead_hours must be a positive integer")
    contract = mpas.get("forecast_contract")
    if not isinstance(contract, dict):
        raise StageConfigurationError("source MPAS case must declare forecast_contract")

    run_hours = int(contract.get("run_hours", -1))
    if run_hours != lead_hours:
        raise StageConfigurationError(
            "mpas.forecast_contract.run_hours must equal mpas.lead_hours"
        )

    interval = int(contract.get("da_state_interval_hours", -1))
    if interval <= 0 or lead_hours % interval:
        raise StageConfigurationError(
            "mpas.forecast_contract.da_state_interval_hours must be positive "
            "and divide mpas.lead_hours"
        )

    mpi_ranks = int(contract.get("mpi_ranks", -1))
    if mpi_ranks <= 0:
        raise StageConfigurationError(
            "mpas.forecast_contract.mpi_ranks must be a positive integer"
        )
    partition = contract.get("partition")
    if not isinstance(partition, str) or not partition.strip():
        raise StageConfigurationError(
            "mpas.forecast_contract.partition must be a non-empty string"
        )

    for key in ("do_restart", "do_DAcycling"):
        if not isinstance(contract.get(key), bool):
            raise StageConfigurationError(
                f"mpas.forecast_contract.{key} must be boolean"
            )
    if "IAU" not in contract:
        raise StageConfigurationError("mpas.forecast_contract must declare IAU")


def _absolutize_mpas_assets(mpas: dict[str, Any], source_case: Path) -> None:
    for entry in mpas.get("templates", []):
        if isinstance(entry, dict):
            entry["source"] = absolutize_case_path(entry.get("source"), source_case)
    directories = mpas.get("link_directories", [])
    for index, entry in enumerate(directories):
        if isinstance(entry, dict):
            entry["source"] = absolutize_case_path(entry.get("source"), source_case)
        elif isinstance(entry, str):
            directories[index] = absolutize_case_path(entry, source_case)
    for entry in mpas.get("links", []):
        if isinstance(entry, dict):
            entry["source"] = absolutize_case_path(entry.get("source"), source_case)


def _patch_initial_mpas(source_case: Path, destination: Path) -> None:
    """Materialize a standalone MPAS integration that produces the first background."""
    source_case = source_case.resolve()
    data = load_yaml(source_case / "mpas.yaml")
    mpas = data.get("mpas")
    if not isinstance(mpas, dict):
        raise StageConfigurationError("initial MPAS mpas.yaml must define mpas mapping")
    lead_hours = int(mpas.get("lead_hours", -1))
    if lead_hours < 6:
        raise StageConfigurationError("initial MPAS integration must cover at least 6 hours")
    pbs = mpas.get("pbs")
    if not isinstance(pbs, dict):
        raise StageConfigurationError("initial MPAS configuration must define pbs")
    mpas["run_dir"] = str(
        destination.resolve() / "work/initialization/mpas/{cycle_id}"
    )
    _absolutize_mpas_assets(mpas, source_case)
    write_yaml(destination / "initialization/mpas.yaml", data)


def _patch_cycling_mpas(source_case: Path, destination: Path) -> None:
    source_case = source_case.resolve()
    data = load_yaml(source_case / "mpas.yaml")
    mpas = data.get("mpas")
    if not isinstance(mpas, dict):
        raise StageConfigurationError("mpas.yaml must define mpas mapping")
    _validate_cycling_contract(mpas)
    pbs = mpas.get("pbs")
    if not isinstance(pbs, dict):
        raise StageConfigurationError("MPAS configuration must define pbs")
    if int(pbs.get("mpiprocs", 0)) != int(mpas["forecast_contract"]["mpi_ranks"]):
        raise StageConfigurationError(
            "mpas.pbs.mpiprocs must match mpas.forecast_contract.mpi_ranks"
        )
    pbs["setup"] = []
    mpas["run_dir"] = str(destination.resolve() / "work/mpas/{cycle_id}")
    _absolutize_mpas_assets(mpas, source_case)

    # The analysis-to-forecast handoff is declared by the MPAS case itself.
    # The materializer only relocates relative assets; it does not infer a
    # scientific product from filenames or method names.
    write_yaml(destination / "mpas.yaml", data)


def _patch_jedi_native(destination: Path, start_cycle: str) -> None:
    path = destination / "jedi.yaml"
    data = load_yaml(path)
    jedi = data.get("jedi")
    if not isinstance(jedi, dict):
        raise StageConfigurationError("jedi.yaml must define jedi mapping")
    root = destination.resolve() / "work"
    jedi["run_dir"] = str(root / "jedi/{cycle_id}")
    cycle = jedi.setdefault("cycle", {})
    cycle["first_cycle"] = _iso(_parse_cycle(start_cycle))

    background = jedi.get("background")
    if not isinstance(background, dict):
        raise StageConfigurationError("jedi.background must be a mapping")
    normalized_trajectory = str(root / "background/{cycle_id}/trajectory.nc")
    background["initial_source"] = normalized_trajectory
    background["source"] = normalized_trajectory

    base = jedi.get("analysis_base_state")
    if not isinstance(base, dict):
        raise StageConfigurationError("jedi.analysis_base_state must be a mapping")
    base["source"] = str(root / "background/{cycle_id}/state.nc")
    target = base.get("target")
    if not isinstance(target, str) or not target:
        raise StageConfigurationError(
            "jedi.analysis_base_state.target must declare the analysis-state filename"
        )
    expected_count = base.get("expected_variable_count")
    if expected_count is not None and not (
        isinstance(expected_count, int) and not isinstance(expected_count, bool)
        or isinstance(expected_count, dict)
    ):
        raise StageConfigurationError(
            "jedi.analysis_base_state.expected_variable_count must be an integer "
            "or a first_cycle/cycling mapping when declared"
        )

    links = jedi.get("links", [])
    if not isinstance(links, list):
        raise StageConfigurationError("jedi.links must be a list")
    pbs = jedi.get("pbs")
    if not isinstance(pbs, dict):
        raise StageConfigurationError("JEDI configuration must define pbs")
    if int(pbs.get("mpiprocs", 0)) <= 0:
        raise StageConfigurationError("jedi.pbs.mpiprocs must be a positive integer")
    write_yaml(path, data)


def _declared_observation_outputs(path: Path) -> list[str]:
    data = load_yaml(path)
    obs = data.get("obs2ioda")
    if not isinstance(obs, dict):
        raise StageConfigurationError("obs2ioda.yaml must define obs2ioda mapping")
    converters = obs.get("converters")
    if not isinstance(converters, list) or not converters:
        raise StageConfigurationError("obs2ioda.converters must be a non-empty list")
    outputs: list[str] = []
    for index, converter in enumerate(converters):
        if not isinstance(converter, dict):
            raise StageConfigurationError(
                f"obs2ioda.converters[{index}] must be a mapping"
            )
        declared = converter.get("outputs")
        if not isinstance(declared, list) or not declared:
            raise StageConfigurationError(
                f"obs2ioda.converters[{index}].outputs must be a non-empty list"
            )
        for output in declared:
            if not isinstance(output, str) or not output:
                raise StageConfigurationError(
                    f"obs2ioda.converters[{index}].outputs must contain strings"
                )
            prefix = "{work_dir}/"
            outputs.append(output[len(prefix):] if output.startswith(prefix) else output)
    return outputs


def _declared_analysis_output(path: Path) -> str:
    data = load_yaml(path)
    jedi = data.get("jedi")
    if not isinstance(jedi, dict):
        raise StageConfigurationError("jedi.yaml must define jedi mapping")
    base = jedi.get("analysis_base_state")
    if not isinstance(base, dict):
        raise StageConfigurationError("jedi.analysis_base_state must be a mapping")
    target = base.get("target")
    if not isinstance(target, str) or not target:
        raise StageConfigurationError(
            "jedi.analysis_base_state.target must declare the analysis-state filename"
        )
    return target


def materialize_corrected_campaign(
    *,
    cycling_jedi_case: Path,
    initial_mpas_case: Path,
    mpas_case: Path,
    obs2ioda_config: Path,
    destination: Path,
    start_cycle: str = None,
    end_cycle: str,
    run_mpas_on_last_cycle: bool = False,
    initial_jedi_case: Path | None = None,
    cycle_interval_hours: int = 6,
) -> Path:
    """Create a clean compact campaign without executing scientific work.

    ``initial_jedi_case`` is accepted only as a source-compatibility argument
    for older callers.  The compact campaign no longer consumes its precomputed
    background or observations; the formal MPAS initialization and current-cycle
    Obs2IODA tasks produce those inputs inside the campaign.
    """
    del initial_jedi_case
    cycles = _cycles(start_cycle, end_cycle, cycle_interval_hours)
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"campaign destination already exists: {destination}")

    try:
        copy_clean_case(cycling_jedi_case.resolve(), destination)
        (destination / "initialization").mkdir(parents=True, exist_ok=True)
        _patch_jedi_native(destination, start_cycle)
        _patch_initial_mpas(initial_mpas_case.resolve(), destination)
        _patch_cycling_mpas(mpas_case.resolve(), destination)
        obs_data = load_yaml(obs2ioda_config.resolve())
        obs = obs_data.get("obs2ioda")
        if not isinstance(obs, dict):
            raise StageConfigurationError("obs2ioda.yaml must define obs2ioda mapping")
        obs["work_dir"] = str(destination.resolve() / "work/obs/{cycle_yyyymmddhh}")
        write_yaml(destination / "obs2ioda.yaml", obs_data)

        workflow = build_corrected_campaign_workflow(
            start_cycle=start_cycle,
            end_cycle=end_cycle,
            experiment_dir=str(destination),
            run_mpas_on_last_cycle=run_mpas_on_last_cycle,
            cycle_interval_hours=cycle_interval_hours,
            observation_outputs=_declared_observation_outputs(destination / "obs2ioda.yaml"),
            analysis_output=_declared_analysis_output(destination / "jedi.yaml"),
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
                        "cycle_interval_hours": cycle_interval_hours,
                        "analysis_cycles": len(cycles),
                        "forecast_legs_for_cycling": len(cycles) - 1,
                        "run_mpas_on_last_cycle": run_mpas_on_last_cycle,
                        "duration_hours": int(
                            (cycles[-1] - cycles[0]).total_seconds() // 3600
                        ),
                    }
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return destination
