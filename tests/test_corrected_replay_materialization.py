from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.corrected_replay import materialize_corrected_replay


def _write_yaml(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _jedi_case(root: Path, inputs: Path, *, initial: bool) -> Path:
    root.mkdir(parents=True)
    (root / "runtime-skeleton").mkdir()
    (root / "runtime-skeleton/fixed.tbl").write_text("fixed", encoding="utf-8")
    obs = {
        "sondes": inputs / "sondes.h5",
        "sfc": inputs / "sfc.h5",
        "gnssro": inputs / "gnssro.h5",
    }
    for path in obs.values():
        path.write_bytes(path.name.encode())
    trajectory = inputs / "trajectory21.nc"
    base = inputs / "base00.nc"
    trajectory.write_bytes(b"trajectory")
    base.write_bytes(b"base")

    links = [
        {"source": str(obs["sondes"]), "target": "Data/ufo/sondes_obs_{analysis_yyyymmddhh}_m.nc4"},
        {"source": str(obs["sfc"]), "target": "Data/ufo/sfc_obs_{analysis_yyyymmddhh}_m.nc4"},
        {"source": str(obs["gnssro"]), "target": "Data/ufo/gnssro_obs_{analysis_yyyymmddhh}_s.nc4"},
    ]
    data = {
        "jedi": {
            "cycle": {
                "step_hours": 6,
                "background_offset_hours": -3,
                "window_hours": 6,
                "first_cycle": "2018-04-15T00:00:00Z",
            },
            "run_dir": "work/jedi/{cycle_id}",
            "runtime": {"skeleton": "runtime-skeleton"},
            "background": {
                "initial_source": str(trajectory),
                "source": "/old/mpas/{previous_cycle_id}/mpasout.{background_mpas_file_time}.nc",
                "target": "background/mpasout.{background_mpas_file_time}.nc",
            },
            "analysis_base_state": {
                "source": str(base) if initial else "/old/base/{analysis_mpas_file_time}.nc",
                "target": "Data/states/mpas.3dvar.{analysis_mpas_file_time}.nc",
                "required_variables": ["rho"],
            },
            "links": links,
            "templates": [],
            "pbs": {
                "queue": "pesqmini",
                "select": 1,
                "ncpus": 128,
                "mpiprocs": 128,
                "walltime": "00:30:00",
                "launcher": "mpiexec",
                "command": ["/bin/true"],
            },
            "validation": {
                "log": "jedi.stdout.log",
                "required_log_markers": ["OOPS Ending"],
                "required_outputs": [
                    {"role": "analysis", "path": "Data/states/mpas.3dvar.{analysis_mpas_file_time}.nc"}
                ],
            },
        }
    }
    _write_yaml(root / "jedi.yaml", data)
    return root


def _mpas_case(root: Path) -> Path:
    root.mkdir()
    (root / "templates").mkdir()
    (root / "templates/namelist.in").write_text("x", encoding="utf-8")
    (root / "templates/streams.in").write_text("x", encoding="utf-8")
    static = root / "static.tbl"
    static.write_text("static", encoding="utf-8")
    data = {
        "mpas": {
            "lead_hours": 6,
            "run_dir": "old/{cycle_id}",
            "forecast_contract": {
                "run_hours": 6,
                "da_state_interval_hours": 3,
                "mpi_ranks": 128,
                "partition": "x1.10242.graph.info.part.128",
                "do_restart": False,
                "do_DAcycling": True,
                "IAU": "off",
            },
            "links": [
                {"source": "/old/analysis.nc", "target": "mpas.analysis-full.{mpas_file_time}.nc"},
                {"source": str(static), "target": "static.tbl"},
            ],
            "templates": [
                {"source": "templates/namelist.in", "target": "namelist.atmosphere"},
                {"source": "templates/streams.in", "target": "streams.atmosphere"},
            ],
            "pbs": {
                "queue": "pesqmidi",
                "ncpus": 128,
                "mpiprocs": 128,
                "walltime": "02:00:00",
                "setup": ["/old/stale/load_jaci_env.sh"],
                "command": ["./mpas_atmosphere"],
            },
            "validation": {
                "log": "log.atmosphere.0000.out",
                "required_log_markers": ["Finished"],
                "required_outputs": [
                    "mpasout.{mpas_t_plus_3_file_time}.nc",
                    "mpasout.{mpas_valid_file_time}.nc",
                ],
            },
        }
    }
    _write_yaml(root / "mpas.yaml", data)
    return root


def _obs_config(path: Path) -> Path:
    _write_yaml(
        path,
        {
            "obs2ioda": {
                "work_dir": "/old/obs/{cycle_id}",
                "converters": [
                    {"name": "prepbufr-conventional", "inputs": [], "outputs": [], "argv": ["true"]},
                    {"name": "gpsro-gnssro", "inputs": [], "outputs": [], "argv": ["true"]},
                ],
            }
        },
    )
    return path


def _workflow(path: Path) -> Path:
    _write_yaml(
        path,
        {
            "workflow": {"name": "replay"},
            "context": {"experiment_dir": "/placeholder"},
            "tasks": [{"name": "noop", "argv": ["true"]}],
        },
    )
    return path


def test_materialize_corrected_replay_isolated_namespace(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    initial = _jedi_case(tmp_path / "jedi00", inputs, initial=True)
    cycling = _jedi_case(tmp_path / "jedi18", inputs, initial=False)
    mpas = _mpas_case(tmp_path / "mpas12")
    obs = _obs_config(tmp_path / "obs2ioda.yaml")
    workflow = _workflow(tmp_path / "workflow.yaml")
    destination = tmp_path / "replay"

    result = materialize_corrected_replay(
        initial_jedi_case=initial,
        cycling_jedi_case=cycling,
        mpas_case=mpas,
        obs2ioda_config=obs,
        workflow_template=workflow,
        destination=destination,
    )

    assert result == destination.resolve()
    replay_root = destination / "work"
    assert (replay_root / "mpas/20180414T180000Z/mpasout.2018-04-14_21.00.00.nc").is_symlink()
    assert (replay_root / "mpas/20180414T180000Z/mpasout.2018-04-15_00.00.00.nc").is_symlink()
    assert (replay_root / "obs/2018041500/sondes_obs_2018041500.h5").is_symlink()
    assert (replay_root / "obs/2018041500/sfc_obs_2018041500.h5").is_symlink()
    assert (replay_root / "obs/2018041500/gnssro_obs_2018041500.h5").is_symlink()

    jedi = yaml.safe_load((destination / "jedi.yaml").read_text())["jedi"]
    assert jedi["run_dir"] == str(replay_root / "jedi/{cycle_id}")
    assert str(replay_root) in jedi["background"]["source"]
    assert str(replay_root) in jedi["analysis_base_state"]["source"]
    assert jedi["analysis_base_state"]["expected_variable_count"] == {
        "first_cycle": 62,
        "cycling": 63,
    }
    assert all("/old/" not in str(item.get("source", "")) for item in jedi["links"])

    mpas_data = yaml.safe_load((destination / "mpas.yaml").read_text())["mpas"]
    assert mpas_data["run_dir"] == str(replay_root / "mpas/{cycle_id}")
    assert mpas_data["pbs"]["setup"] == []
    analysis = next(item for item in mpas_data["links"] if item["target"].startswith("mpas.analysis-full"))
    assert str(replay_root / "jedi") in analysis["source"]

    obs_data = yaml.safe_load((destination / "obs2ioda.yaml").read_text())["obs2ioda"]
    assert obs_data["work_dir"] == str(replay_root / "obs/{cycle_yyyymmddhh}")

    wf = yaml.safe_load((destination / "workflow.yaml").read_text())
    assert wf["context"]["experiment_dir"] == str(destination.resolve())


def test_materialize_refuses_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "replay"
    destination.mkdir()
    with pytest.raises(FileExistsError, match="already exists"):
        materialize_corrected_replay(
            initial_jedi_case=tmp_path / "missing",
            cycling_jedi_case=tmp_path / "missing",
            mpas_case=tmp_path / "missing",
            obs2ioda_config=tmp_path / "missing.yaml",
            workflow_template=tmp_path / "missing-workflow.yaml",
            destination=destination,
        )
