"""NMC preflight tests for configured MPAS NetCDF contracts."""

from __future__ import annotations

from pathlib import Path

from netCDF4 import Dataset

from monan_jedi_workflow.components.bmatrix.nmc_pairs.stage import NmcPairsStage
from monan_jedi_workflow.core.stage import RunContext


def _state(path: Path, valid_time: str, *, mesh_id: str = "x1.10242") -> None:
    """Create a small MPAS-like state with a canonical character time field."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with Dataset(path, "w", format="NETCDF4") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("nCells", 2)
        dataset.createDimension("StrLen", 19)
        dataset.setncattr("mesh_id", mesh_id)
        dataset.createVariable("temperature", "f8", ("Time", "nCells"))[:] = 273.15
        xtime = dataset.createVariable("xtime", "S1", ("Time", "StrLen"))
        xtime[0, :] = list(valid_time)


def test_nmc_rejects_structurally_incompatible_existing_state_files(tmp_path: Path) -> None:
    """The manifest stage must reject incompatible state files before publication."""
    config = {
        "model": {
            "mpas": {
                "forecast_products": {
                    "root": str(tmp_path / "products"),
                    "restart_template": "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
                    "state_template": "{init_yyyymmddhh}/f{lead_hours_03d}/state.{mpas_valid_file_time}.nc",
                },
                "artifact_validation": {
                    "forecast_state": {
                        "consumer": "bmatrix.bflow",
                        "accepted_formats": ["cdf5"],
                        "required_variables": ["temperature", "xtime"],
                        "required_dimensions": {"nCells": 2},
                        "required_global_attributes": {"mesh_id": "x1.10242"},
                        "time_variable": "xtime",
                        "require_expected_time": True,
                    }
                },
            }
        },
        "bmatrix": {
            "nmc_pairs": {
                "start_valid_time": "2026-06-22T00:00:00Z",
                "end_valid_time": "2026-06-25T00:00:00Z",
            }
        },
    }
    context = RunContext("bmatrix", "nmc-netcdf", tmp_path / "workspace", config=config)
    stage = NmcPairsStage.from_context(context)
    for pair in stage.pairs():
        for member in (pair.older, pair.newer):
            member.restart.parent.mkdir(parents=True, exist_ok=True)
            member.restart.write_bytes(b"restart")
            _state(member.state, pair.valid_time)

    report = stage.validate_inputs(context)
    assert not report.is_valid
    assert any(issue.code == "netcdf.format" for issue in report.issues)
