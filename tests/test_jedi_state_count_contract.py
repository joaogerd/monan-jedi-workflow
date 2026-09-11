from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from netCDF4 import Dataset

from monan_jedi_workflow.jedi_stage import (
    _initialize_analysis_output,
    load_jedi_run,
)
from monan_jedi_workflow.stage_config import StageConfigurationError


def _write_state(path: Path, variable_count: int, *, refl10cm: bool = False) -> None:
    if variable_count < 1:
        raise ValueError("variable_count must be positive")

    path.parent.mkdir(parents=True, exist_ok=True)
    with Dataset(path, "w") as dataset:
        dataset.createDimension("nCells", 1)
        dataset.createVariable("rho", "f4", ("nCells",))[:] = 1.0

        reserved = {"rho"}
        if refl10cm:
            dataset.createVariable("refl10cm", "f4", ("nCells",))[:] = 0.0
            reserved.add("refl10cm")

        remaining = variable_count - len(reserved)
        for index in range(remaining):
            dataset.createVariable(
                f"field_{index:03d}", "f4", ("nCells",)
            )[:] = float(index)


def _case(
    tmp_path: Path,
    *,
    source: Path,
    expected_variable_count: int | dict[str, int],
) -> Path:
    case = tmp_path / "case"
    case.mkdir()
    data = {
        "jedi": {
            "cycle": {
                "step_hours": 6,
                "background_offset_hours": -3,
                "window_hours": 6,
                "first_cycle": "2018-04-15T00:00:00Z",
            },
            "run_dir": str(tmp_path / "work/jedi/{cycle_id}"),
            "analysis_base_state": {
                "source": str(source),
                "target": "Data/states/analysis.{analysis_mpas_file_time}.nc",
                "required_variables": ["rho"],
                "expected_variable_count": expected_variable_count,
            },
            "pbs": {},
        }
    }
    (case / "jedi.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )
    return case


def test_state_count_mapping_uses_first_cycle_value(tmp_path: Path) -> None:
    state = tmp_path / "state00.nc"
    _write_state(state, 62)
    case = _case(
        tmp_path,
        source=state,
        expected_variable_count={"first_cycle": 62, "cycling": 63},
    )

    run = load_jedi_run(case, "2018-04-15T00:00:00Z")
    manifest = _initialize_analysis_output(run)

    assert manifest is not None
    assert manifest["variable_count"] == 62
    assert manifest["expected_variable_count"] == 62
    assert manifest["expected_variable_count_rule"] == "first_cycle"


def test_state_count_mapping_uses_cycling_value(tmp_path: Path) -> None:
    state = tmp_path / "state06.nc"
    _write_state(state, 63, refl10cm=True)
    case = _case(
        tmp_path,
        source=state,
        expected_variable_count={"first_cycle": 62, "cycling": 63},
    )

    run = load_jedi_run(case, "2018-04-15T06:00:00Z")
    manifest = _initialize_analysis_output(run)

    assert manifest is not None
    assert manifest["variable_count"] == 63
    assert manifest["expected_variable_count"] == 63
    assert manifest["expected_variable_count_rule"] == "cycling"


def test_state_count_mapping_rejects_wrong_cycle_count(tmp_path: Path) -> None:
    state = tmp_path / "wrong06.nc"
    _write_state(state, 62)
    case = _case(
        tmp_path,
        source=state,
        expected_variable_count={"first_cycle": 62, "cycling": 63},
    )

    run = load_jedi_run(case, "2018-04-15T06:00:00Z")
    with pytest.raises(
        StageConfigurationError,
        match=r"found 62, expected 63",
    ):
        _initialize_analysis_output(run)


def test_scalar_contract_does_not_silently_accept_refl10cm_schema_change(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state06.nc"
    _write_state(state, 63, refl10cm=True)
    case = _case(
        tmp_path,
        source=state,
        expected_variable_count=62,
    )

    run = load_jedi_run(case, "2018-04-15T06:00:00Z")
    with pytest.raises(
        StageConfigurationError,
        match=r"found 63, expected 62",
    ):
        _initialize_analysis_output(run)
