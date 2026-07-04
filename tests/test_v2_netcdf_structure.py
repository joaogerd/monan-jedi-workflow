"""Tests for structural NetCDF validation contracts."""

from __future__ import annotations

from pathlib import Path

from netCDF4 import Dataset

from monan_jedi_workflow.core.netcdf import NetcdfFormat
from monan_jedi_workflow.core.netcdf_validation import NetcdfStructureContract, validate_netcdf_structure


def _state_file(path: Path) -> None:
    """Create a minimal MPAS-like state fixture with a character time value."""
    with Dataset(path, "w", format="NETCDF4") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("nCells", 4)
        dataset.createDimension("StrLen", 19)
        dataset.setncattr("mesh_id", "x1.10242")
        state = dataset.createVariable("temperature", "f8", ("Time", "nCells"))
        state[:] = 273.15
        xtime = dataset.createVariable("xtime", "S1", ("Time", "StrLen"))
        xtime[0, :] = list("2026-06-22_00:00:00")


def test_netcdf_structure_accepts_matching_contract(tmp_path: Path) -> None:
    """Required variables, dimensions, attributes, format, and time validate."""
    path = tmp_path / "state.nc"
    _state_file(path)
    contract = NetcdfStructureContract(
        consumer="bmatrix.bflow",
        accepted_formats=(NetcdfFormat.NETCDF4,),
        required_variables=("temperature", "xtime"),
        required_dimensions={"Time": 1, "nCells": 4},
        required_global_attributes={"mesh_id": "x1.10242"},
        time_variable="xtime",
        expected_time="2026-06-22_00:00:00",
    )
    assert validate_netcdf_structure(path, contract).is_valid


def test_netcdf_structure_reports_multiple_contract_violations(tmp_path: Path) -> None:
    """A preflight report includes all failed schema expectations."""
    path = tmp_path / "state.nc"
    _state_file(path)
    contract = NetcdfStructureContract(
        consumer="bmatrix.bflow",
        accepted_formats=(NetcdfFormat.CDF5,),
        required_variables=("u",),
        required_dimensions={"nCells": 5, "nVertLevels": None},
        required_global_attributes={"mesh_id": "x1.40962", "grid_uuid": None},
        time_variable="xtime",
        expected_time="2026-06-23_00:00:00",
    )
    report = validate_netcdf_structure(path, contract)
    codes = {issue.code for issue in report.issues}
    assert not report.is_valid
    assert {"netcdf.format", "netcdf.variable", "netcdf.dimension_size", "netcdf.dimension", "netcdf.attribute_value", "netcdf.attribute", "netcdf.time_value"}.issubset(codes)
