"""Materialize a clean corrected 00Z->18Z replay case for simpleWorkflow.

The materializer intentionally reuses only configuration/static assets and the
declared first-cycle starting inputs.  Forecasts, analyses and IODA products
for 06/12/18 are generated inside the new replay namespace.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from .jedi_stage import load_jedi_run
from .stage_config import StageConfigurationError, render_text, resolve_path

_FIRST_CYCLE = "2018-04-15T00:00:00Z"
_INITIAL_PREVIOUS_ID = "20180414T180000Z"
_FORBIDDEN_CASE_NAMES = (
    "jedi.stdout.log",
    "jedi.stderr.log",
    "stdout.log",
    "stderr.log",
)
_FORBIDDEN_CASE_PREFIXES = (
    "mpasout.",
    "obsout_",
    "mpas.3dvar.",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise StageConfigurationError(f"YAML root must be a mapping: {path}")
    return value


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _assert_clean_case_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if ".monan-jedi-workflow" in path.parts:
            raise StageConfigurationError(
                f"source case contains runtime control state and is not clean: {path}"
            )
        if not path.is_file() and not path.is_symlink():
            continue
        if path.name in _FORBIDDEN_CASE_NAMES or path.name.startswith(_FORBIDDEN_CASE_PREFIXES):
            raise StageConfigurationError(
                f"source case contains a cycle-dependent scientific/runtime product: {path}"
            )


def _copy_clean_case(source: Path, destination: Path) -> None:
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"source case directory does not exist: {source}")
    _assert_clean_case_tree(source)
    shutil.copytree(source, destination, symlinks=True)


def _safe_initial_link(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"declared first-cycle input does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"clean replay target already exists: {target}")
    target.symlink_to(source.resolve())


def _resolved_link_source(run, entry: dict[str, Any], index: int) -> Path:
    return resolve_path(
        entry.get("source"),
        config_dir=run.config_dir,
        context=run.context,
        label=f"jedi.links[{index}].source",
    )


def _initial_inputs(initial_jedi_case: Path) -> dict[str, Path]:
    run = load_jedi_run(initial_jedi_case, _FIRST_CYCLE)
    background = run.config.get("background")
    if not isinstance(background, dict):
        raise StageConfigurationError("initial JEDI case is missing jedi.background")
    initial_source = background.get("initial_source")
    if not isinstance(initial_source, str) or not initial_source:
        raise StageConfigurationError(
            "initial JEDI case is missing jedi.background.initial_source"
        )
    result: dict[str, Path] = {
        "trajectory": resolve_path(
            initial_source,
            config_dir=run.config_dir,
            context=run.context,
            label="jedi.background.initial_source",
        )
    }

    base = run.config.get("analysis_base_state")
    if not isinstance(base, dict):
        raise StageConfigurationError(
            "initial JEDI case must declare jedi.analysis_base_state"
        )
    result["analysis_base"] = resolve_path(
        base.get("source"),
        config_dir=run.config_dir,
        context=run.context,
        label="jedi.analysis_base_state.source",
    )

    for index, raw in enumerate(run.config.get("links", [])):
        if not isinstance(raw, dict):
            continue
        target_value = raw.get("target")
        if not isinstance(target_value, str):
            continue
        target = render_text(
            target_value,
            run.context,
            label=f"jedi.links[{index}].target",
        ).lower()
        role = None
        if "sondes_obs" in target:
            role = "sondes"
        elif "sfc_obs" in target:
            role = "sfc"
        elif "gnssro_obs" in target:
            role = "gnssro"
        if role is not None:
            result[role] = _resolved_link_source(run, raw, index)

    missing = [name for name in ("sondes", "sfc", "gnssro") if name not in result]
    if missing:
        raise StageConfigurationError(
            "initial JEDI case does not expose required baseline observation links: "
            + ", ".join(missing)
        )
    return result


def _patch_jedi(destination: Path, replay_root: Path) -> None:
    path = destination / "jedi.yaml"
    data = _load_yaml(path)
    jedi = data.get("jedi")
    if not isinstance(jedi, dict):
        raise StageConfigurationError("jedi.yaml must define jedi mapping")
    jedi["run_dir"] = str(replay_root / "jedi/{cycle_id}")

    cycle = jedi.setdefault("cycle", {})
    cycle["first_cycle"] = _FIRST_CYCLE

    background = jedi.get("background")
    if not isinstance(background, dict):
        raise StageConfigurationError("jedi.background must be a mapping")
    background["initial_source"] = str(
        replay_root
        / f"mpas/{_INITIAL_PREVIOUS_ID}/mpasout.2018-04-14_21.00.00.nc"
    )
    background["source"] = str(
        replay_root / "mpas/{previous_cycle_id}/mpasout.{background_mpas_file_time}.nc"
    )

    base = jedi.get("analysis_base_state")
    if not isinstance(base, dict):
        raise StageConfigurationError("jedi.analysis_base_state must be a mapping")
    base["source"] = str(
        replay_root / "mpas/{previous_cycle_id}/mpasout.{analysis_mpas_file_time}.nc"
    )
    base["target"] = "Data/states/mpas.3dvar.{analysis_mpas_file_time}.nc"

    found = set()
    links = jedi.get("links", [])
    if not isinstance(links, list):
        raise StageConfigurationError("jedi.links must be a list")
    for entry in links:
        if not isinstance(entry, dict):
            continue
        target = str(entry.get("target", "")).lower()
        if "sondes_obs" in target:
            entry["source"] = str(
                replay_root / "obs/{analysis_yyyymmddhh}/sondes_obs_{analysis_yyyymmddhh}.h5"
            )
            found.add("sondes")
        elif "sfc_obs" in target:
            entry["source"] = str(
                replay_root / "obs/{analysis_yyyymmddhh}/sfc_obs_{analysis_yyyymmddhh}.h5"
            )
            found.add("sfc")
        elif "gnssro_obs" in target:
            entry["source"] = str(
                replay_root / "obs/{analysis_yyyymmddhh}/gnssro_obs_{analysis_yyyymmddhh}.h5"
            )
            found.add("gnssro")
    if found != {"sondes", "sfc", "gnssro"}:
        raise StageConfigurationError(
            "cycling JEDI case must declare sondes, sfc and gnssro links"
        )

    pbs = jedi.get("pbs")
    if not isinstance(pbs, dict) or int(pbs.get("mpiprocs", 0)) != 128:
        raise StageConfigurationError("corrected replay requires JEDI pbs.mpiprocs=128")

    _write_yaml(path, data)


def _absolutize_case_path(value: Any, source_case: Path) -> Any:
    if not isinstance(value, str) or not value:
        return value
    if "{" in value:
        return value
    path = Path(value)
    return str(path if path.is_absolute() else (source_case / path).resolve())


def _patch_mpas(source_case: Path, destination: Path, replay_root: Path) -> None:
    source_path = source_case.resolve() / "mpas.yaml"
    data = _load_yaml(source_path)
    mpas = data.get("mpas")
    if not isinstance(mpas, dict):
        raise StageConfigurationError("mpas.yaml must define mpas mapping")

    if int(mpas.get("lead_hours", -1)) != 6:
        raise StageConfigurationError("corrected replay requires mpas.lead_hours=6")
    contract = mpas.get("forecast_contract")
    expected = {
        "run_hours": 6,
        "da_state_interval_hours": 3,
        "mpi_ranks": 128,
        "partition": "x1.10242.graph.info.part.128",
        "do_restart": False,
        "do_DAcycling": True,
        "IAU": "off",
    }
    if not isinstance(contract, dict) or any(contract.get(k) != v for k, v in expected.items()):
        raise StageConfigurationError(
            "source MPAS case does not satisfy the validated corrected forecast_contract"
        )
    pbs = mpas.get("pbs")
    if not isinstance(pbs, dict) or int(pbs.get("mpiprocs", 0)) != 128:
        raise StageConfigurationError("corrected replay requires MPAS pbs.mpiprocs=128")

    mpas["run_dir"] = str(replay_root / "mpas/{cycle_id}")

    templates = mpas.get("templates", [])
    for entry in templates:
        if isinstance(entry, dict):
            entry["source"] = _absolutize_case_path(entry.get("source"), source_case)

    directories = mpas.get("link_directories", [])
    for index, entry in enumerate(directories):
        if isinstance(entry, dict):
            entry["source"] = _absolutize_case_path(entry.get("source"), source_case)
        elif isinstance(entry, str) and "{" not in entry:
            directories[index] = _absolutize_case_path(entry, source_case)

    analysis_link_found = False
    links = mpas.get("links", [])
    for entry in links:
        if not isinstance(entry, dict):
            continue
        target = str(entry.get("target", ""))
        if target.startswith("mpas.analysis-full.") or target == "init.nc":
            entry["source"] = str(
                replay_root
                / "jedi/{cycle_id}/Data/states/mpas.3dvar.{mpas_file_time}.nc"
            )
            entry["target"] = "mpas.analysis-full.{mpas_file_time}.nc"
            analysis_link_found = True
        else:
            entry["source"] = _absolutize_case_path(entry.get("source"), source_case)
    if not analysis_link_found:
        raise StageConfigurationError(
            "source MPAS case does not declare the analysis initial-condition link"
        )

    _write_yaml(destination / "mpas.yaml", data)


def _patch_obs(source_config: Path, destination: Path, replay_root: Path) -> None:
    data = _load_yaml(source_config.resolve())
    obs = data.get("obs2ioda")
    if not isinstance(obs, dict):
        raise StageConfigurationError("obs2ioda.yaml must define obs2ioda mapping")
    obs["work_dir"] = str(replay_root / "obs/{cycle_yyyymmddhh}")
    converters = obs.get("converters", [])
    names = {item.get("name") for item in converters if isinstance(item, dict)}
    if not {"prepbufr-conventional", "gpsro-gnssro"}.issubset(names):
        raise StageConfigurationError(
            "corrected replay Obs2IODA config must include prepbufr-conventional and gpsro-gnssro"
        )
    _write_yaml(destination / "obs2ioda.yaml", data)


def _patch_workflow(template: Path, destination: Path) -> None:
    data = _load_yaml(template.resolve())
    context = data.setdefault("context", {})
    if not isinstance(context, dict):
        raise StageConfigurationError("simpleWorkflow context must be a mapping")
    context["experiment_dir"] = str(destination.resolve())
    _write_yaml(destination / "workflow.yaml", data)


def materialize_corrected_replay(
    *,
    initial_jedi_case: Path,
    cycling_jedi_case: Path,
    mpas_case: Path,
    obs2ioda_config: Path,
    workflow_template: Path,
    destination: Path,
) -> Path:
    """Create a clean, non-executed 00Z->18Z replay case."""
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"replay destination already exists: {destination}")

    inputs = _initial_inputs(initial_jedi_case.resolve())
    _copy_clean_case(cycling_jedi_case.resolve(), destination)
    replay_root = destination / "work"

    try:
        _patch_jedi(destination, replay_root)
        _patch_mpas(mpas_case.resolve(), destination, replay_root)
        _patch_obs(obs2ioda_config.resolve(), destination, replay_root)
        _patch_workflow(workflow_template.resolve(), destination)

        initial_mpas = replay_root / "mpas" / _INITIAL_PREVIOUS_ID
        _safe_initial_link(
            inputs["trajectory"],
            initial_mpas / "mpasout.2018-04-14_21.00.00.nc",
        )
        _safe_initial_link(
            inputs["analysis_base"],
            initial_mpas / "mpasout.2018-04-15_00.00.00.nc",
        )
        initial_obs = replay_root / "obs" / "2018041500"
        _safe_initial_link(inputs["sondes"], initial_obs / "sondes_obs_2018041500.h5")
        _safe_initial_link(inputs["sfc"], initial_obs / "sfc_obs_2018041500.h5")
        _safe_initial_link(inputs["gnssro"], initial_obs / "gnssro_obs_2018041500.h5")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return destination
