from pathlib import Path
import pytest
import yaml
from monan_jedi_workflow.experiment_start import create_experiment


def test_installed_recipe_creates_independent_case(tmp_path):
    root = tmp_path / 'case'
    create_experiment(root)
    config = yaml.safe_load((root / 'science/jedi.yaml').read_text())['jedi']
    assert all('EDITAR' not in p.read_text() for p in root.rglob('*.yaml'))
    assert config['pbs']['mpiprocs'] == 128
    assert (root / 'science/templates/variational.yaml').is_file()
    first = root / 'work/background/20250901T000000Z/trajectory.nc'
    assert first.readlink() == root / 'work/initialization/mpas/20250831T180000Z/mpasout.2025-08-31_21.00.00.nc'
    assert 'scientific_pilot' not in (root / 'run-case.pbs').read_text()
    assert 'wps-run' in (root / 'run-case.pbs').read_text()
    with pytest.raises(FileExistsError):
        create_experiment(root)


def test_native_variable_dependencies_resolve_in_order(tmp_path, monkeypatch):
    from monan_jedi_workflow.stage_config import render_declared_variables
    from monan_jedi_workflow.cycle_context import parse_cycle_time
    monkeypatch.setenv('MONAN_JEDI_INSTALL_ROOT', '/test/install')
    monkeypatch.setenv('STACK_ROOT', '/test/stack')
    for name in ['INPUT', 'MESH', 'PHYSICS', 'BMATRIX', 'GFS', 'LIBFABRIC']:
        monkeypatch.setenv(f'MONAN_{name}_ROOT', '/test/'+name)
    monkeypatch.setattr('monan_jedi_workflow.stage_config.runtime_contract_context', lambda *a: {})
    root=tmp_path/'case';create_experiment(root)
    for file,key in [('science/mpas.yaml','mpas'),('science/obs2ioda.yaml','obs2ioda')]:
        cfg=yaml.safe_load((root/file).read_text())[key]
        resolved=render_declared_variables(cfg,parse_cycle_time('2025-09-01T00:00:00Z').render_context(),label=key)
        assert resolved['experiment_root']==str(root)
