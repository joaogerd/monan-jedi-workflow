"""End-to-end local test for the V2 NMC campaign workflow."""

from __future__ import annotations

import sys
from pathlib import Path

from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner
from monan_jedi_workflow.platforms.local import LocalProcessBackend
from monan_jedi_workflow.workflows.nmc_campaign import build_nmc_campaign


def _write_programs(workspace: Path) -> None:
    """Write deterministic MPAS-like initialization and forecast fixture programs."""
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "fake_init.py").write_text(
        """from pathlib import Path
import sys
from netCDF4 import Dataset
path = Path(sys.argv[1]); stamp = sys.argv[2]
path.parent.mkdir(parents=True, exist_ok=True)
with Dataset(path, 'w', format='NETCDF4') as ds:
    ds.createDimension('Time', 1); ds.createDimension('nCells', 2); ds.createDimension('StrLen', 19)
    ds.setncattr('mesh_id', 'x1.10242')
    xtime = ds.createVariable('xtime', 'S1', ('Time', 'StrLen'))
    xtime[0, :] = [item.encode() for item in stamp]
print('Initialization complete')
""",
        encoding="utf-8",
    )
    (workspace / "fake_forecast.py").write_text(
        """from pathlib import Path
import sys
from netCDF4 import Dataset
restart, state, stamp = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
for path, state_file in ((restart, False), (state, True)):
    path.parent.mkdir(parents=True, exist_ok=True)
    with Dataset(path, 'w', format='NETCDF4') as ds:
        ds.createDimension('Time', 1); ds.createDimension('nCells', 2); ds.createDimension('StrLen', 19)
        ds.setncattr('mesh_id', 'x1.10242')
        xtime = ds.createVariable('xtime', 'S1', ('Time', 'StrLen'))
        xtime[0, :] = [item.encode() for item in stamp]
        if state_file:
            ds.createVariable('temperature', 'f8', ('Time', 'nCells'))[:] = 273.15
print('Forecast complete')
""",
        encoding="utf-8",
    )


def test_full_nmc_campaign_runs_locally_with_structural_netcdf_validation(tmp_path: Path) -> None:
    """The complete V2 chain publishes a valid BFLOW manifest and is restart-safe."""
    workspace = tmp_path / "workspace"
    _write_programs(workspace)
    config = {
        "case": {"name": "full-local-nmc"},
        "model": {
            "mpas": {
                "initialization_products": {
                    "root": str(tmp_path / "initial-products"),
                    "state_template": "{init_yyyymmddhh}/init.{mpas_valid_file_time}.nc",
                },
                "initialization": {
                    "run_dir": "runs/init/{init_yyyymmddhh}",
                    "argv": [sys.executable, "{workspace}/fake_init.py", "{state}", "{cycle_time}"],
                    "validation": {"log": "stdout.log", "required_log_markers": ["Initialization complete"]},
                },
                "forecast_products": {
                    "root": str(tmp_path / "forecast-products"),
                    "restart_template": "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
                    "state_template": "{init_yyyymmddhh}/f{lead_hours_03d}/state.{mpas_valid_file_time}.nc",
                },
                "forecast": {
                    "run_dir": "runs/forecast/{init_yyyymmddhh}/f{lead_hours_03d}",
                    "argv": [sys.executable, "{workspace}/fake_forecast.py", "{restart}", "{state}", "{valid_time}"],
                    "links": [{"source": "{initial_state}", "target": "initial_state.nc"}],
                    "validation": {"log": "stdout.log", "required_log_markers": ["Forecast complete"]},
                },
                "artifact_validation": {
                    "initialization_state": {
                        "accepted_formats": ["netcdf4"],
                        "required_variables": ["xtime"],
                        "required_dimensions": {"Time": 1, "nCells": 2},
                        "required_global_attributes": {"mesh_id": "x1.10242"},
                        "time_variable": "xtime",
                        "require_expected_time": True,
                    },
                    "forecast_restart": {
                        "accepted_formats": ["netcdf4"],
                        "required_variables": ["xtime"],
                        "required_dimensions": {"Time": 1, "nCells": 2},
                        "required_global_attributes": {"mesh_id": "x1.10242"},
                        "time_variable": "xtime",
                        "require_expected_time": True,
                    },
                    "forecast_state": {
                        "accepted_formats": ["netcdf4"],
                        "required_variables": ["temperature", "xtime"],
                        "required_dimensions": {"Time": 1, "nCells": 2},
                        "required_global_attributes": {"mesh_id": "x1.10242"},
                        "time_variable": "xtime",
                        "require_expected_time": True,
                    },
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
    context = RunContext("bmatrix", "full-local-nmc", workspace, config=config)
    plan = build_nmc_campaign(context, backend=LocalProcessBackend())
    runner = LocalWorkflowRunner(plan.specification, plan.stages)

    results = runner.run(context)
    manifest = workspace / "artifacts/bmatrix/nmc_pairs/bflow-manifest.tsv"
    assert len(results) == 14
    assert manifest.is_file()
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == 5
    assert runner.run(context) == ()
