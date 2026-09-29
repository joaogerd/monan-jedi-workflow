from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from netCDF4 import Dataset

from monan_jedi_workflow.mpas_stage import MPASValidationError, prepare_mpas, validate_mpas
from monan_jedi_workflow.netcdf_validation import NetcdfStructureContract, validate_netcdf_structure


def _write_mpas_state(path: Path, timestamp: str) -> None:
    with Dataset(path, "w", format="NETCDF3_64BIT_DATA") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("StrLen", 64)
        dataset.createDimension("nCells", 2)
        xtime = dataset.createVariable("xtime", "S1", ("Time", "StrLen"))
        # MPAS character timestamps may carry an informational units attribute.
        xtime.units = "MPAS character timestamp"
        raw = np.frombuffer(timestamp.encode("ascii").ljust(64, b"\x00"), dtype="S1").reshape(1, 64)
        xtime[:] = raw
        dataset.createVariable("theta", "f8", ("Time", "nCells"))
        dataset.mesh_id = "test-mesh"


def test_mpas_character_xtime_is_validated_as_character_data(tmp_path: Path) -> None:
    path = tmp_path / "state.nc"
    _write_mpas_state(path, "2018-04-15_06:00:00")
    issues = validate_netcdf_structure(
        path,
        NetcdfStructureContract(
            consumer="next-cycle",
            required_variables=("theta", "xtime"),
            required_dimensions={"Time": 1, "nCells": 2},
            required_global_attributes={"mesh_id": "test-mesh"},
            time_variable="xtime",
            expected_time="2018-04-15_06:00:00",
        ),
    )
    assert issues == []


def test_validate_mpas_reports_wrong_scientific_time(tmp_path: Path) -> None:
    case = tmp_path / "case"
    case.mkdir()
    executable = case / "mpas_atmosphere"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    (case / "mpas.yaml").write_text(
        f"""mpas:
  lead_hours: 6
  run_dir: {case}/run/{{cycle_id}}
  links:
    - {{source: {executable}, target: mpas_atmosphere}}
  pbs:
    queue: test
    mpiprocs: 1
    walltime: '00:10:00'
    command: [./mpas_atmosphere]
  validation:
    log: stdout.log
    required_log_markers: [Finished]
    required_outputs: ["mpasout.{{mpas_valid_file_time}}.nc"]
    netcdf:
      - path: mpasout.{{mpas_valid_file_time}}.nc
        consumer: next MPAS-JEDI cycle
        required_variables: [theta, xtime]
        required_dimensions:
          Time: 1
          nCells: 2
        required_global_attributes:
          mesh_id: test-mesh
        time_variable: xtime
        expected_time: "{{mpas_valid_time}}"
""",
        encoding="utf-8",
    )
    run = prepare_mpas(case, "2018-04-15T00:00:00Z")
    run.manifest_path.write_text(
        json.dumps({"job_id": "123.test", "state": "completed"}) + "\n",
        encoding="utf-8",
    )
    (run.run_dir / "stdout.log").write_text("Finished\n", encoding="utf-8")
    _write_mpas_state(run.run_dir / "mpasout.2018-04-15_06.00.00.nc", "2018-04-15_03:00:00")

    with pytest.raises(MPASValidationError, match="does not contain 2018-04-15_06:00:00"):
        validate_mpas(case, "2018-04-15T00:00:00Z")

    report = json.loads((run.run_dir / ".monan-jedi-workflow/mpas-validation.json").read_text())
    assert report["valid"] is False
    assert len(report["netcdf_issues"]) == 1
