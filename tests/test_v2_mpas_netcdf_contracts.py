"""Tests for MPAS NetCDF artifact validation configuration."""

from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.components.model.mpas import (
    compile_mpas_forecast,
    compile_mpas_initialization,
)
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def _config(root: Path) -> dict[str, object]:
    """Build a minimal MPAS configuration with structural artifact contracts."""
    return {
        "model": {
            "mpas": {
                "initialization_products": {
                    "root": str(root / "init"),
                    "state_template": "init.{mpas_valid_file_time}.nc",
                },
                "initialization": {"run_dir": "runs/init/{init_yyyymmddhh}", "argv": ["/bin/true"]},
                "forecast_products": {
                    "root": str(root / "forecast"),
                    "restart_template": "restart.{mpas_valid_file_time}.nc",
                    "state_template": "state.{mpas_valid_file_time}.nc",
                },
                "forecast": {"run_dir": "runs/forecast/{init_yyyymmddhh}", "argv": ["/bin/true"]},
                "artifact_validation": {
                    "initialization_state": {
                        "consumer": "model.mpas.forecast",
                        "required_variables": ["xtime"],
                        "time_variable": "xtime",
                        "require_expected_time": True,
                    },
                    "forecast_state": {
                        "consumer": "bmatrix.bflow",
                        "accepted_formats": ["cdf5"],
                        "required_variables": ["temperature", "xtime"],
                        "required_dimensions": {"nCells": 10242},
                        "required_global_attributes": {"mesh_id": "x1.10242"},
                        "time_variable": "xtime",
                        "require_expected_time": True,
                    },
                },
            }
        }
    }


def test_forecast_compiler_attaches_state_netcdf_contract(tmp_path: Path) -> None:
    """Forecast state checks must preserve the expected valid time."""
    stage = compile_mpas_forecast(
        _config(tmp_path),
        workspace=tmp_path,
        init_time="2026-06-20T00:00:00Z",
        lead_hours=48,
        backend=LocalProcessBackend(),
    )
    assert len(stage.contract.netcdf_checks) == 1
    check = stage.contract.netcdf_checks[0]
    assert check.path == stage.product.state
    assert check.contract.consumer == "bmatrix.bflow"
    assert check.contract.expected_time == "2026-06-22_00:00:00"


def test_initialization_compiler_attaches_cycle_time_contract(tmp_path: Path) -> None:
    """Initialization checks must preserve the expected cycle time."""
    stage = compile_mpas_initialization(
        _config(tmp_path),
        workspace=tmp_path,
        cycle_time="2026-06-20T00:00:00Z",
        backend=LocalProcessBackend(),
    )
    assert len(stage.contract.netcdf_checks) == 1
    assert stage.contract.netcdf_checks[0].contract.expected_time == "2026-06-20_00:00:00"
