from pathlib import Path

import numpy as np
from netCDF4 import Dataset

from monan_jedi_workflow.netcdf_compare import compare_netcdf, main


def _write(path: Path, *, file_id: str, offset: float = 0.0) -> None:
    with Dataset(path, "w") as ds:
        ds.createDimension("nCells", 4)
        ds.setncattr("file_id", file_id)
        ds.setncattr("config_test", "same")
        var = ds.createVariable("temperature", "f8", ("nCells",))
        var.setncattr("units", "K")
        var[:] = np.array([280.0, 281.0, 282.0, 283.0]) + offset


def test_exact_comparison_ignores_file_id_by_default(tmp_path: Path) -> None:
    ref = tmp_path / "ref.nc"
    new = tmp_path / "new.nc"
    _write(ref, file_id="reference")
    _write(new, file_id="candidate")

    report = compare_netcdf(ref, new)

    assert report.equivalent
    assert report.variables_compared == 1
    assert report.variables_identical == 1


def test_file_id_can_be_compared_explicitly(tmp_path: Path) -> None:
    ref = tmp_path / "ref.nc"
    new = tmp_path / "new.nc"
    _write(ref, file_id="reference")
    _write(new, file_id="candidate")

    report = compare_netcdf(ref, new, ignore_global_attrs=())

    assert not report.equivalent
    assert any("global attribute file_id" in item for item in report.differences)


def test_numeric_tolerance_is_optional(tmp_path: Path) -> None:
    ref = tmp_path / "ref.nc"
    new = tmp_path / "new.nc"
    _write(ref, file_id="reference")
    _write(new, file_id="candidate", offset=1.0e-10)

    exact = compare_netcdf(ref, new)
    tolerant = compare_netcdf(ref, new, rtol=0.0, atol=2.0e-10)

    assert not exact.equivalent
    assert exact.data_differences
    assert tolerant.equivalent


def test_cli_exit_status(tmp_path: Path, capsys) -> None:
    ref = tmp_path / "ref.nc"
    same = tmp_path / "same.nc"
    different = tmp_path / "different.nc"
    _write(ref, file_id="one")
    _write(same, file_id="two")
    _write(different, file_id="three", offset=1.0)

    assert main([str(ref), str(same)]) == 0
    assert "[OK] NetCDF scientific contents are equivalent." in capsys.readouterr().out

    assert main([str(ref), str(different)]) == 1
    output = capsys.readouterr().out
    assert "[DIFF]" in output
    assert "temperature: data differ" in output


def test_nested_ioda_groups_are_compared(tmp_path: Path) -> None:
    paths = [tmp_path / 'reference.nc', tmp_path / 'candidate.nc']
    for index, path in enumerate(paths):
        with Dataset(path, 'w') as ds:
            ds.createDimension('Location', 2)
            group = ds.createGroup('hofx1').createGroup('nested')
            var = group.createVariable('airTemperature', 'f8', ('Location',))
            var[:] = [280., 281. + index]
    report = compare_netcdf(*paths)
    assert not report.equivalent
    assert report.variables_compared == 1
    assert any('/hofx1/nested/airTemperature' in d for d in report.data_differences)


def test_group_inventory_and_metadata_are_compared(tmp_path: Path) -> None:
    paths = [tmp_path / 'reference.nc', tmp_path / 'candidate.nc']
    for index, path in enumerate(paths):
        with Dataset(path, 'w') as ds:
            group = ds.createGroup('ObsValue')
            group.setncattr('source', str(index))
            if index:
                ds.createGroup('EffectiveQC1')
    report = compare_netcdf(*paths)
    assert not report.equivalent
    assert any('group inventory' in d for d in report.differences)
    assert any('/ObsValue' in d and 'source' in d for d in report.differences)
