from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys

import netCDF4
import pytest
import yaml


def script():
    path = Path(__file__).parents[1] / 'scripts/generate_campaign_figures.py'
    spec = spec_from_file_location('campaign_figures', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quadratic_cost_uses_initial_nonlinear_cost_and_excludes_components():
    result = script().parse_cost('''CostFunction: Nonlinear J = 100.0
Quadratic cost function: J ( 1) = 8.0e1
Quadratic cost function: Jb ( 1) = 12.0
Quadratic cost function: JoJc( 1) = 68.0
Quadratic cost function: J ( 2) = 7.0D1
CostFunction: Nonlinear J = 73.0
OOPS Ending
''')
    assert result == [(0, 100.0), (1, 80.0), (2, 70.0)]


def test_repeated_outer_loop_is_not_silently_combined():
    with pytest.raises(ValueError, match='outer'):
        script().parse_cost('''CostFunction: Nonlinear J = 100
Quadratic cost function: J (1) = 80
Quadratic cost function: J (1) = 60
''')


def test_feedback_statistics_use_identical_qc_and_missing_value_mask(tmp_path):
    path = tmp_path / 'obsout.nc4'
    with netCDF4.Dataset(path, 'w') as f:
        f.createDimension('Location', 4)
        for group, values in {
            'ObsValue': [280, 282, 999, 280],
            'hofx0': [278, 280, 100, -999],
            'hofx1': [279, 281, 100, 279],
            'EffectiveQC0': [0, 0, 7, 0],
            'EffectiveQC1': [0, 0, 0, 0],
        }.items():
            v = f.createGroup(group).createVariable('airTemperature', 'f8', ('Location',), fill_value=-999)
            v[:] = values
    result = script().observation_stats([path])
    assert result['nobs'] == 2
    assert result['omb_rmse'] == 2
    assert result['oma_rmse'] == 1
    assert result['qc_groups'] == 'EffectiveQC0+EffectiveQC1'


def test_missing_qc_is_reported_explicitly(tmp_path):
    path = tmp_path / 'obsout.nc4'
    with netCDF4.Dataset(path, 'w') as f:
        f.createDimension('Location', 1)
        for name in ('ObsValue', 'hofx0', 'hofx1'):
            f.createGroup(name).createVariable('airTemperature', 'f8', ('Location',))[:] = [280]
    with pytest.raises(ValueError, match='QC'):
        script().observation_stats([path])


def test_complete_campaign_generates_three_figures_and_records_real_counts(tmp_path):
    case = tmp_path / 'case'
    case.mkdir()
    (case / 'campaign-request.yaml').write_text(yaml.safe_dump({'campaign': {
        'start': '2025-09-01T00:00:00Z', 'end': '2025-09-01T06:00:00Z',
        'cycle_interval_hours': 6}}))
    state = case / '.simpleworkflow/state.sqlite3'
    state.parent.mkdir()
    with sqlite3.connect(state) as db:
        db.execute('create table task_state(cycle_id text, task text, status text)')
        db.execute('create table run_history(id integer)')
        db.execute('create table attempt_history(id integer)')
        db.execute('insert into run_history values(1)')
        for cid in ('20250901T000000Z', '20250901T060000Z'):
            db.execute('insert into task_state values(?,?,?)', (cid, 'observations_run', 'success'))
            run = case / 'work/jedi' / cid
            control = run / '.monan-jedi-workflow'
            control.mkdir(parents=True)
            log = run / 'jedi.stdout.log'
            log.write_text('CostFunction: Nonlinear J = 100\nQuadratic cost function: J (1) = 80\nOOPS Ending\n')
            (control / 'jedi-validation.json').write_text(json.dumps({'valid': True, 'cycle_id': cid, 'log': str(log)}))
            feedback = run / 'Data/os/obsout_3dvar_sondes.nc4'
            feedback.parent.mkdir(parents=True)
            with netCDF4.Dataset(feedback, 'w') as f:
                f.createDimension('Location', 2)
                for group, values in {'ObsValue': [280, 282], 'hofx0': [278, 280],
                                      'hofx1': [279, 281], 'EffectiveQC': [0, 0]}.items():
                    f.createGroup(group).createVariable('airTemperature', 'f8', ('Location',))[:] = values
            obs = case / 'work/obs' / cid.replace('T', '')[:10] / '.monan-jedi-workflow'
            obs.mkdir(parents=True)
            (obs / 'obs2ioda-validation.json').write_text(json.dumps({'valid': True, 'cycle_id': cid}))
        mpas = case / 'work/mpas/20250901T000000Z/.monan-jedi-workflow'
        mpas.mkdir(parents=True)
        (mpas / 'mpas-validation.json').write_text(json.dumps({'valid': True, 'cycle_id': '20250901T000000Z'}))
    path = Path(__file__).parents[1] / 'scripts/generate_campaign_figures.py'
    run = subprocess.run([sys.executable, str(path), str(case)], capture_output=True, text=True, env=os.environ.copy())
    assert run.returncode == 0, run.stderr
    summary = json.loads((case / 'diagnostics/diagnostic_summary.json').read_text())
    assert summary['obs2ioda_conversions'] == 2  # Not inferred from 1 forecast leg.
    assert summary['mean_omb_rmse'] == 2
    assert summary['mean_oma_rmse'] == 1
    assert len(list((case / 'diagnostics/figures').glob('*.png'))) == 3
    assert len(list((case / 'diagnostics/figures').glob('*.pdf'))) == 3
    assert len(list((case / 'diagnostics/figures').glob('*.svg'))) == 3
    assert len(list((case / 'diagnostics').glob('*.csv'))) == 4
    repeated = subprocess.run([sys.executable, str(path), str(case)], capture_output=True, text=True)
    assert repeated.returncode == 2
    assert 'output already exists' in repeated.stderr
