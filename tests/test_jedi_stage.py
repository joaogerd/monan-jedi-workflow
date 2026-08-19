import json
from pathlib import Path

import pytest
import yaml
from netCDF4 import Dataset

from monan_jedi_workflow.jedi_stage import (
    JEDIValidationError,
    prepare_jedi,
    validate_jedi,
)
from monan_jedi_workflow.stage_config import StageConfigurationError


def _case(tmp_path: Path) -> tuple[Path, Path]:
    config = tmp_path / "case"
    config.mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    forecast = tmp_path / "forecast"
    forecast.mkdir()

    initial = inputs / "initial.nc"
    initial.write_text("initial", encoding="utf-8")

    skeleton = inputs / "skeleton"
    skeleton.mkdir()
    (skeleton / "fixed.tbl").write_text("fixed", encoding="utf-8")

    template = inputs / "variational.yaml.in"
    template.write_text(
        "analysis: {analysis_time}\nbackground: {background_time}\n",
        encoding="utf-8",
    )

    data = {
        "jedi": {
            "cycle": {
                "step_hours": 6,
                "background_offset_hours": -3,
                "window_hours": 6,
                "first_cycle": "2018-04-15T00:00:00Z",
            },
            "variables": {
                "root": str(tmp_path),
                "forecast_root": str(forecast),
            },
            "run_dir": "{root}/work/jedi/{cycle_id}",
            "runtime": {"skeleton": str(skeleton)},
            "background": {
                "initial_source": str(initial),
                "source": (
                    "{forecast_root}/{previous_cycle_id}/"
                    "mpasout.{background_mpas_file_time}.nc"
                ),
                "target": (
                    "background/mpasout.{background_mpas_file_time}.nc"
                ),
            },
            "templates": [
                {"source": str(template), "target": "variational.yaml"}
            ],
            "pbs": {
                "queue": "pesqmini",
                "select": 1,
                "ncpus": 64,
                "mpiprocs": 64,
                "walltime": "00:30:00",
                "launcher": "mpiexec",
                "command": ["/bin/echo", "variational.yaml"],
            },
            "validation": {
                "log": "jedi.stdout.log",
                "required_log_markers": ["OOPS Ending"],
                "required_outputs": [
                    {
                        "role": "analysis",
                        "path": (
                            "Data/states/analysis."
                            "{analysis_mpas_file_time}.nc"
                        ),
                    }
                ],
            },
        }
    }
    (config / "jedi.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )
    return config, forecast


def test_prepare_first_cycle_uses_external_background(tmp_path: Path) -> None:
    config, _ = _case(tmp_path)

    run = prepare_jedi(config, "2018-04-15T00:00:00Z")

    background = (
        run.run_dir / "background/mpasout.2018-04-14_21.00.00.nc"
    )
    assert background.is_symlink()
    assert (run.run_dir / "fixed.tbl").is_file()
    assert (run.run_dir / "variational.yaml").read_text(
        encoding="utf-8"
    ).startswith("analysis: 2018-04-15T00:00:00Z")
    assert run.pbs_path.is_file()
    manifest = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    assert manifest["state"] == "prepared"


def test_prepare_subsequent_cycle_uses_previous_forecast(tmp_path: Path) -> None:
    config, forecast = _case(tmp_path)
    source = (
        forecast
        / "20180415T000000Z"
        / "mpasout.2018-04-15_03.00.00.nc"
    )
    source.parent.mkdir(parents=True)
    source.write_text("background", encoding="utf-8")

    run = prepare_jedi(config, "2018-04-15T06:00:00Z")

    link = run.run_dir / "background/mpasout.2018-04-15_03.00.00.nc"
    assert link.resolve() == source.resolve()


def test_validate_publishes_analysis_artifact(tmp_path: Path) -> None:
    config, _ = _case(tmp_path)
    run = prepare_jedi(config, "2018-04-15T00:00:00Z")

    manifest = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    manifest["job_id"] = "123.jaci"
    run.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    (run.run_dir / "jedi.stdout.log").write_text(
        "... OOPS Ending ...", encoding="utf-8"
    )
    output = run.run_dir / "Data/states/analysis.2018-04-15_00.00.00.nc"
    output.parent.mkdir(parents=True)
    output.write_text("analysis", encoding="utf-8")

    validate_jedi(config, "2018-04-15T00:00:00Z")

    artifact = json.loads(run.artifacts_path.read_text(encoding="utf-8"))
    assert artifact["valid"] is True
    assert artifact["artifacts"][0]["role"] == "analysis"
    assert artifact["artifacts"][0]["path"] == str(output)


def test_validate_rejects_missing_scientific_success(tmp_path: Path) -> None:
    config, _ = _case(tmp_path)
    run = prepare_jedi(config, "2018-04-15T00:00:00Z")
    manifest = json.loads(run.manifest_path.read_text(encoding="utf-8"))
    manifest["job_id"] = "123.jaci"
    run.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(JEDIValidationError, match="missing log marker"):
        validate_jedi(config, "2018-04-15T00:00:00Z")


def test_runtime_skeleton_cannot_silently_change(tmp_path: Path) -> None:
    config, _ = _case(tmp_path)
    prepare_jedi(config, "2018-04-15T00:00:00Z")

    data = yaml.safe_load((config / "jedi.yaml").read_text(encoding="utf-8"))
    other = tmp_path / "other-skeleton"
    other.mkdir()
    data["jedi"]["runtime"]["skeleton"] = str(other)
    (config / "jedi.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )

    with pytest.raises(StageConfigurationError, match="different skeleton"):
        prepare_jedi(config, "2018-04-15T00:00:00Z")


def test_analysis_output_is_atomically_preseeded_with_full_state(tmp_path: Path) -> None:
    config, _ = _case(tmp_path)
    seed = tmp_path / "inputs/full-state.nc"
    with Dataset(seed, "w", format="NETCDF3_64BIT_DATA") as dataset:
        dataset.createDimension("nCells", 2)
        dataset.createVariable("rho", "f4", ("nCells",))[:] = [1.0, 2.0]
        dataset.createVariable("skintemp", "f4", ("nCells",))[:] = [280.0, 281.0]

    data = yaml.safe_load((config / "jedi.yaml").read_text(encoding="utf-8"))
    data["jedi"]["analysis_seed"] = {
        "source": str(seed),
        "target": "Data/states/analysis.{analysis_mpas_file_time}.nc",
        "required_variables": ["rho", "skintemp"],
        "expected_variable_count": 2,
    }
    (config / "jedi.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    run = prepare_jedi(config, "2018-04-15T00:00:00Z")
    output = run.run_dir / "Data/states/analysis.2018-04-15_00.00.00.nc"
    with Dataset(output) as dataset:
        assert set(dataset.variables) == {"rho", "skintemp"}
        assert dataset.data_model == "NETCDF3_64BIT_DATA"

    # A second preparation is idempotent and cannot create another submission.
    prepare_jedi(config, "2018-04-15T00:00:00Z")
    manifest = json.loads(
        (run.run_dir / ".monan-jedi-workflow/analysis-seed.json").read_text()
    )
    assert manifest["state"] == "already-seeded"
    assert manifest["size_bytes"] == seed.stat().st_size


def test_analysis_seed_rejects_partial_full_state(tmp_path: Path) -> None:
    config, _ = _case(tmp_path)
    seed = tmp_path / "inputs/partial.nc"
    with Dataset(seed, "w") as dataset:
        dataset.createDimension("nCells", 1)
        dataset.createVariable("rho", "f4", ("nCells",))
    data = yaml.safe_load((config / "jedi.yaml").read_text(encoding="utf-8"))
    data["jedi"]["analysis_seed"] = {
        "source": str(seed),
        "target": "Data/states/analysis.{analysis_mpas_file_time}.nc",
        "required_variables": ["rho", "skintemp"],
    }
    (config / "jedi.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(StageConfigurationError, match="missing: skintemp"):
        prepare_jedi(config, "2018-04-15T00:00:00Z")
