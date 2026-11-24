from pathlib import Path
import yaml
import pytest
from monan_jedi_workflow.scientific_pilot import generate_pilot


def test_pilot_uses_candidate_forecast_for_second_analysis(tmp_path):
    reference = tmp_path / 'reference'
    reference.mkdir()
    for directory in ['templates', 'runtime-skeleton']:
        (reference / directory).mkdir()
        (reference / directory / 'unchanged').write_bytes(b'science\n')
    jedi = {'run_dir': '/old/work/jedi/{cycle_id}',
            'cycle': {'step_hours': 6, 'background_offset_hours': -3, 'window_hours': 6,
                      'first_cycle': '2025-09-01T00:00:00Z'},
            'background': {'source': '/old/trajectory', 'initial_source': '/old/trajectory'},
            'analysis_base_state': {'source': '/old/state'},
            'links': [{'source': 'work/obs/{analysis_yyyymmddhh}/sondes.h5', 'target': 'obs.h5'}],
            'templates': [], 'runtime': {'skeleton': 'runtime-skeleton'},
            'variables': {}, 'pbs': {'mpiprocs': 128}}
    model = {'variables': {'campaign_root': '/old'}, 'run_dir': '/old/work/mpas/{cycle_id}',
             'templates': [{'source': '/old/templates/namelist.in', 'target': 'namelist'}],
             'pbs': {'mpiprocs': 128}}
    for name, section in [('jedi', jedi), ('mpas', model)]:
        (reference / f'{name}.yaml').write_text(yaml.safe_dump({name: section}))
    destination = tmp_path / 'pilot'
    generate_pilot(reference, destination)
    first = destination / 'work/background/20250901T000000Z/trajectory.nc'
    second = destination / 'work/background/20250901T060000Z/trajectory.nc'
    assert first.readlink() == reference / 'work/background/20250901T000000Z/trajectory.nc'
    assert second.readlink() == destination / 'work/mpas/20250901T000000Z/mpasout.2025-09-01_03.00.00.nc'
    state = second.parent / 'state.nc'
    assert state.readlink() == destination / 'work/mpas/20250901T000000Z/mpasout.2025-09-01_06.00.00.nc'
    science = yaml.safe_load((destination / 'science/jedi.yaml').read_text())['jedi']
    assert science['pbs']['mpiprocs'] == 128
    assert science['links'][0]['source'].startswith(str(reference))
    assert (destination / 'science/templates/unchanged').read_bytes() == b'science\n'
    assert yaml.safe_load((destination / 'campaign.yaml').read_text())['last_cycle']['forecast'] is False
    with pytest.raises(FileExistsError):
        generate_pilot(reference, destination)


def test_pilot_refuses_destination_inside_reference(tmp_path):
    with pytest.raises(ValueError, match='overlap'):
        generate_pilot(tmp_path, tmp_path / 'child')


@pytest.mark.parametrize('first', [0, 1])
def test_cost_parser_accepts_reference_iterations_and_rejects_repeated_attempt(tmp_path, first):
    from monan_jedi_workflow.scientific_pilot import _costs
    log = tmp_path / 'jedi.log'
    content = 'CostFunction: Nonlinear J = 100\n'
    content += '\n'.join(f'Quadratic cost function: J ({i}) = {100-i}' for i in range(first, 11))
    log.write_text(content)
    assert len(_costs(log)['quadratic']) == 11-first
    log.write_text(content + '\n' + content)
    with pytest.raises(ValueError):
        _costs(log)


def test_compare_requires_all_products_and_detects_grouped_difference(tmp_path):
    import json
    from netCDF4 import Dataset
    from monan_jedi_workflow.scientific_pilot import compare_pilot, CYCLES
    reference, candidate = tmp_path / 'reference', tmp_path / 'candidate'
    candidate.mkdir()
    (candidate / 'pilot.json').write_text(json.dumps({'reference': str(reference)}))
    assert compare_pilot(candidate)['passed'] is False
    for root in (reference, candidate):
        for cid, hour in zip(CYCLES, ('00', '06')):
            base = root / 'work/jedi' / cid
            products = [base / f'Data/states/mpas.3dfgat.2025-09-01_{hour}.00.00.nc']
            products += [base / f'Data/os/obsout_3dvar_{kind}.nc4' for kind in ('sondes', 'sfc', 'gnssroref')]
            for path in products:
                path.parent.mkdir(parents=True, exist_ok=True)
                with Dataset(path, 'w') as ds:
                    ds.createDimension('Location', 1)
                    for name in ['ObsValue', 'hofx0', 'hofx1', 'EffectiveQC']:
                        var = ds.createGroup(name).createVariable('airTemperature', 'f8', ('Location',))
                        var.units = 'K'
                        var[:] = [0 if name == 'EffectiveQC' else 280]
            (base / 'jedi.stdout.log').write_text('CostFunction: Nonlinear J = 100\n' + '\n'.join(
                f'Quadratic cost function: J ({i}) = {100-i}' for i in range(1, 11)))
        for hour in ('03', '06'):
            path = root / 'work/mpas' / CYCLES[0] / f'mpasout.2025-09-01_{hour}.00.00.nc'
            path.parent.mkdir(parents=True, exist_ok=True)
            with Dataset(path, 'w') as ds:
                ds.createVariable('temperature', 'f8')[:] = 280
    assert compare_pilot(candidate)['passed'] is True
    path = candidate / 'work/jedi' / CYCLES[1] / 'Data/os/obsout_3dvar_sfc.nc4'
    with Dataset(path, 'a') as ds:
        ds['hofx1/airTemperature'][:] = 281
    assert compare_pilot(candidate)['passed'] is False
