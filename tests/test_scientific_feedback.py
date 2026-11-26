import numpy as np
import pytest
from netCDF4 import Dataset
from monan_jedi_workflow.scientific_feedback import paired_feedback


def test_paired_feedback_uses_intersection_and_masks(tmp_path):
    path = tmp_path / 'feedback.nc4'
    with Dataset(path, 'w') as ds:
        ds.createDimension('Location', 5)
        values = {'ObsValue': [280, 280, 280, 280, -999],
                  'hofx0': [282, 282, 290, 290, 290],
                  'hofx1': [281, 281, 290, 290, 290],
                  'EffectiveQC0': [0, 0, 1, 0, 0],
                  'EffectiveQC1': [0, 0, 0, 1, 0]}
        for group, data in values.items():
            var = ds.createGroup(group).createVariable('airTemperature', 'f8', ('Location',), fill_value=-999)
            if not group.startswith('EffectiveQC'):
                var.units = 'K'
            var[:] = data
    result = paired_feedback(path, 'airTemperature')
    assert result['n'] == 2
    assert result['omb_rmse'] == 2
    assert result['oma_rmse'] == 1
    assert result['omb_bias'] == -2
    with Dataset(path, 'a') as ds:
        ds['hofx1/airTemperature'].units = 'C'
    with pytest.raises(ValueError, match='units'):
        paired_feedback(path, 'airTemperature')


def test_feedback_without_qc_is_rejected(tmp_path):
    path = tmp_path / 'feedback.nc4'
    with Dataset(path, 'w') as ds:
        ds.createDimension('Location', 1)
        for name in ['ObsValue', 'hofx0', 'hofx1']:
            var = ds.createGroup(name).createVariable('airTemperature', 'f8', ('Location',))
            var.units = 'K'
            var[:] = [280]
    with pytest.raises(ValueError, match='QC'):
        paired_feedback(path, 'airTemperature')


def test_unattributed_ioda_missing_sentinel_is_excluded(tmp_path):
    path = tmp_path / 'feedback.nc4'
    with Dataset(path, 'w') as ds:
        ds.createDimension('Location', 2)
        for group in ['ObsValue', 'hofx0', 'hofx1', 'EffectiveQC']:
            var = ds.createGroup(group).createVariable('airTemperature', 'f8', ('Location',), fill_value=False)
            var.units = 'K'
            var[:] = [280, 3.36879526e38] if group == 'ObsValue' else [0, 0] if group == 'EffectiveQC' else [279, 279]
    assert paired_feedback(path, 'airTemperature')['n'] == 1


def test_missing_hofx_unit_attributes_uses_observation_unit(tmp_path):
    """Real JEDI obsout writes units on ObsValue but can omit them on HofX."""
    path = tmp_path / "obsout.nc4"
    with Dataset(path, "w") as ds:
        ds.createDimension("Location", 3)
        for group, values in {
            "ObsValue": [280.0, 281.0, 282.0],
            "hofx0": [279.0, 280.0, 283.0],
            "hofx1": [279.5, 280.5, 282.5],
            "EffectiveQC0": [0, 0, 0],
            "EffectiveQC1": [0, 0, 1],
        }.items():
            variable = ds.createGroup(group).createVariable("airTemperature", "f8", ("Location",))
            if group == "ObsValue":
                variable.units = "K"
            variable[:] = values
    result = paired_feedback(path, "airTemperature")
    assert result["n"] == 2
    assert result["units"] == "K"
    assert result["units_source"] == "ObsValue"
    assert result["omb_bias"] == pytest.approx(1)
    assert result["oma_bias"] == pytest.approx(0.5)


def test_explicit_hofx_unit_mismatch_still_fails(tmp_path):
    path = tmp_path / "obsout.nc4"
    with Dataset(path, "w") as ds:
        ds.createDimension("Location", 1)
        for group, value, units in (
            ("ObsValue", 280.0, "K"),
            ("hofx0", 279.0, None),
            ("hofx1", 278.0, "degC"),
            ("EffectiveQC", 0, None),
        ):
            var = ds.createGroup(group).createVariable("airTemperature", "f8", ("Location",))
            var[:] = [value]
            if units:
                var.units = units
    with pytest.raises(ValueError, match="units"):
        paired_feedback(path, "airTemperature")


def test_missing_observation_unit_still_fails(tmp_path):
    path = tmp_path / "obsout.nc4"
    with Dataset(path, "w") as ds:
        ds.createDimension("Location", 1)
        for group in ("ObsValue", "hofx0", "hofx1", "EffectiveQC"):
            var = ds.createGroup(group).createVariable("airTemperature", "f8", ("Location",))
            var[:] = [0]
    with pytest.raises(ValueError, match="ObsValue units"):
        paired_feedback(path, "airTemperature")
