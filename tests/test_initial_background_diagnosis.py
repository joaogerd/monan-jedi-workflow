from pathlib import Path
import runpy

import numpy as np
from netCDF4 import Dataset

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/diagnose_initial_background.py'))


def test_geometry_diagnosis_detects_vertical_mismatch_with_same_level_count(tmp_path):
    files = [tmp_path/'initial.nc',tmp_path/'invariant.nc']
    for index, path in enumerate(files):
        with Dataset(path,'w') as ds:
            ds.createDimension('nCells',2)
            ds.createDimension('nVertLevelsP1',3)
            ds.createVariable('zgrid','f8',('nCells','nVertLevelsP1'))[:] = [[0,100+index,300],[10,110+index,310]]
            ds.createVariable('latCell','f8',('nCells',))[:] = [0.1,0.2]
    with Dataset(files[0]) as initial,Dataset(files[1]) as invariant:
        result=MODULE['compare_geometry'](initial,invariant)
        assert result['zgrid']['max_abs_difference']==1
        assert not result['zgrid']['close']
        assert result['latCell']['close']


def test_field_diagnosis_reports_masked_and_nonfinite_values(tmp_path):
    path=tmp_path/'initial.nc'
    with Dataset(path,'w') as ds:
        ds.createDimension('Time',1)
        ds.createDimension('nCells',4)
        ds.createVariable('u','f8',('Time','nCells'),fill_value=-999)[:] = [[3,np.nan,np.inf,-999]]
    with Dataset(path) as ds:
        result=MODULE['stats'](ds.variables['u'])
        assert result=={'shape':[4],'masked':1,'nonfinite':2,'min':3.0,'max':3.0}
