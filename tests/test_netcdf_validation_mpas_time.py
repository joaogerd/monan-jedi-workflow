"""Regression tests for MPAS character time validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from netCDF4 import Dataset, stringtochar

from monan_jedi_workflow.core.netcdf import NetcdfFormat
from monan_jedi_workflow.core.netcdf_validation import NetcdfStructureContract, validate_netcdf_structure


def test_character_mpas_xtime_takes_precedence_over_units_attribute(tmp_path: Path) -> None:
    """MPAS xtime is character data even when an informational units attribute exists."""
    path = tmp_path / "mpas-init.nc"
    expected = "2026-06-20_00:00:00"
    with Dataset(path, "w", format="NETCDF3_64BIT_DATA") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("StrLen", 64)
        xtime = dataset.createVariable("xtime", "S1", ("Time", "StrLen"))
        xtime.units = "MPAS character timestamp"
        xtime[:] = stringtochar(np.array([expected], dtype="S64"))

    report = validate_netcdf_structure(
        path,
        NetcdfStructureContract(
            consumer="test",
            accepted_formats=(NetcdfFormat.CDF5,),
            required_variables=("xtime",),
            required_dimensions={"Time": 1, "StrLen": 64},
            time_variable="xtime",
            expected_time=expected,
        ),
    )

    assert report.is_valid
