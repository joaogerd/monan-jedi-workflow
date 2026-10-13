import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def generator():
    spec = importlib.util.spec_from_file_location('create_2025_reference', ROOT/'scripts/create_2025_reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_case_stages_complete_captured_geometry_and_keeps_prepnr(tmp_path):
    source = tmp_path/'tutorial'
    shutil.copytree(ROOT/'examples/case', source)
    obs = (source/'obs2ioda.yaml').read_text().replace('observations/prepbufr/', 'observations/prepnr/')
    (source/'obs2ioda.yaml').write_text(obs)
    profile = (source/'profile.yaml').read_text().replace('/prep48h/', '/prepnr/')
    (source/'profile.yaml').write_text(profile)
    target = tmp_path/'new-case'
    generator().create_case(source, target, check_inputs=False)
    config = yaml.safe_load((target/'jedi.yaml').read_text())['jedi']
    assert config['pbs']['mpiprocs'] == 128
    assert config['pbs']['environment']['GFORTRAN_CONVERT_UNIT'] == 'big_endian:101-200'
    assert 'observations/prepnr/' in (target/'obs2ioda.yaml').read_text()
    assert '/prepnr/' in (target/'profile.yaml').read_text()
    assert config['runtime']['skeleton'] == 'runtime-skeleton'
    assert len([x for x in config['links'] if '{physics_root}/' in x['source']]) == 13
    for suffix in ('outer', 'inner'):
        xml = ET.parse(target/f'templates/streams.atmosphere.jedi.{suffix}.in')
        for entry in xml.iter('file'):
            assert (target/'runtime-skeleton'/entry.attrib['name']).is_file()
    assert 'config_dt = 1200.0' in (target/'templates/namelist.atmosphere.outer.in').read_text()
    assert 'config_dt = 1800.0' in (target/'templates/namelist.atmosphere.inner.in').read_text()
    campaign = yaml.safe_load((target/'campaign.yaml').read_text())['campaign']
    assert campaign['duration'] == 'PT6H'
    assert not any(target.rglob('*.nc'))


def test_reference_assets_have_source_checksums():
    assets = ROOT/'examples/m3-reference-assets'
    manifest = json.loads((assets/'provenance.json').read_text())
    for item in manifest['files']:
        assert hashlib.sha256((assets/item['path']).read_bytes()).hexdigest() == item['sha256']


def test_fresh_case_refuses_existing_destination(tmp_path):
    target = tmp_path/'existing'
    target.mkdir()
    with pytest.raises(FileExistsError):
        generator().create_case(ROOT/'examples/case', target, check_inputs=False)


def test_missing_external_inputs_do_not_leave_half_created_case(tmp_path, monkeypatch):
    module = generator()
    monkeypatch.setenv('MONAN_JEDI_INSTALL_ROOT', str(tmp_path/'missing-install'))
    target = tmp_path/'new-case'
    with pytest.raises((FileNotFoundError, ValueError)):
        module.create_case(ROOT/'examples/case', target, check_inputs=True)
    assert not target.exists()


def test_generated_case_prepares_all_geometry_dependencies(tmp_path, monkeypatch):
    from netCDF4 import Dataset
    import numpy as np
    from monan_jedi_workflow.jedi_stage import prepare_jedi

    install = tmp_path/'install'
    manifest = install/'share/monan-jedi/install-manifest.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'schema_version': 2, 'ecosystem_contract_version': 2,
        'contract': 'monan-jedi-runtime-v2', 'public_anchors': ['MONAN_JEDI_INSTALL_ROOT','STACK_ROOT'],
        'stack': {'env_name':'test', 'env_module':'test/module', 'site_setup':'setup.sh',
                  'module_root_template':'envs/{env_name}/modules'}}))
    monkeypatch.setenv('MONAN_JEDI_INSTALL_ROOT', str(install))
    monkeypatch.setenv('STACK_ROOT', str(tmp_path/'stack'))
    monkeypatch.setenv('USER', 'testuser')
    source = tmp_path/'source'
    shutil.copytree(ROOT/'examples/case', source)
    mesh = tmp_path/'mesh'
    (mesh/'static').mkdir(parents=True)
    (mesh/'partitions').mkdir()
    (mesh/'static/x1.10242.invariant.nc').write_text('test mesh fixture')
    (mesh/'partitions/x1.10242.graph.info.part.128').write_text('0\n1\n')
    physics = tmp_path/'physics'
    physics.mkdir()
    for name in generator().PHYSICS:
        (physics/name).write_text('table fixture')
    path = source/'mpas.yaml'
    cfg = yaml.safe_load(path.read_text())
    cfg['mpas']['variables'].update(mesh_root=str(mesh), physics_root=str(physics))
    path.write_text(yaml.safe_dump(cfg))
    bmatrix = tmp_path/'bmatrix'
    bmatrix.mkdir()
    path = source/'jedi.yaml'
    cfg = yaml.safe_load(path.read_text())
    cfg['jedi']['variables']['bmatrix_root'] = str(bmatrix)
    path.write_text(yaml.safe_dump(cfg))
    case = generator().create_case(source, tmp_path/'new', check_inputs=False)
    for relative, section in [('mpas.yaml', 'mpas'), ('initialization/mpas.yaml', 'mpas'), ('initialization/mpas_init.yaml', 'mpas_init')]:
        stage = yaml.safe_load((case/relative).read_text())[section]
        assert stage['variables']['mesh_root'] == str(mesh)
        if 'physics_root' in stage['variables']:
            assert stage['variables']['physics_root'] == str(physics)
    bg = case/'work/background/20250901T000000Z'
    bg.mkdir(parents=True)
    (bg/'trajectory.nc').write_text('trajectory fixture')
    config = yaml.safe_load((case/'jedi.yaml').read_text())['jedi']
    with Dataset(bg/'state.nc', 'w') as ds:
        ds.createDimension('Time',1)
        ds.createDimension('StrLen',64)
        ds.createDimension('nCells',2)
        text = '2025-09-01_00:00:00'.ljust(64)
        ds.createVariable('xtime','S1',('Time','StrLen'))[:] = np.array(list(text),dtype='S1')[None,:]
        for name in config['analysis_base_state']['required_variables']:
            ds.createVariable(name,'f4',('Time','nCells'))[:] = 1
    obs = case/'work/obs/2025090100'
    obs.mkdir(parents=True)
    for name in ('sondes','sfc','gnssro'):
        (obs/f'{name}_obs_2025090100.h5').write_text('IODA fixture')
    run = prepare_jedi(case, '2025-09-01T00:00:00Z')
    assert run.pbs_path.is_file()
    assert 'mpiexec -n 128' in run.pbs_path.read_text()
    assert (run.run_dir/'templateFields.10242.nc').resolve() == bg/'state.nc'
    for name in ('geovars.yaml','keptvars.yaml','x1.10242.graph.info.part.128',
                 'stream_list.atmosphere.background','testinput/obsop_name_map.yaml'):
        assert (run.run_dir/name).is_file()
    for suffix in ('outer','inner'):
        assert (run.run_dir/f'geometry/2025090100/streams.atmosphere.{suffix}').is_file()
