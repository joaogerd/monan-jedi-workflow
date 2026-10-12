from netCDF4 import Dataset
from monan_jedi_workflow.geometry_validation import compare_vertical_geometry


def test_rejects_different_vertical_grid_even_with_equal_level_count(tmp_path):
    paths=[tmp_path/'state.nc',tmp_path/'invariant.nc']
    for i,path in enumerate(paths):
        with Dataset(path,'w') as ds:
            ds.createDimension('nCells',1)
            ds.createDimension('nVertLevelsP1',3)
            ds.createVariable('zgrid','f8',('nCells','nVertLevelsP1'))[:] = [[0,100+i*350,1000]]
            ds.createVariable('zz','f8',('nCells','nVertLevelsP1'))[:] = [[1,1,1]]
    issues=compare_vertical_geometry(*paths, fields=('zgrid','zz'))
    assert any('zgrid' in issue and '350' in issue for issue in issues)
    assert compare_vertical_geometry(paths[0],paths[0], fields=('zgrid','zz')) == []


def test_init_validation_blocks_existing_state_with_incompatible_geometry(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import pytest
    from monan_jedi_workflow import init_stage
    from monan_jedi_workflow.geometry_validation import FIELDS
    state=tmp_path/'state.nc';reference=tmp_path/'invariant.nc'
    for i,path in enumerate((state,reference)):
        with Dataset(path,'w') as ds:
            ds.createDimension('nCells',1)
            ds.createDimension('nVertLevelsP1',3)
            for field in FIELDS:
                ds.createVariable(field,'f8',('nCells','nVertLevelsP1'))[:] = [[1,100+i*350 if field=='zgrid' else 1,1000]]
    (tmp_path/'init.log').write_text('Finished running the init_atmosphere core')
    run=SimpleNamespace(run_dir=tmp_path,config_dir=tmp_path,context={},
                        manifest_path=tmp_path/'mpas-init.json',cycle=SimpleNamespace(cycle_time='2025-08-31T18:00:00Z'),
                        config={'validation': {'log':'init.log','required_log_markers':['Finished running the init_atmosphere core'],
                                               'required_outputs':[str(state)],'geometry_reference':str(reference)}})
    monkeypatch.setattr(init_stage,'_load',lambda *_:run)
    monkeypatch.setattr(init_stage,'_read',lambda *_:{'job_id':'123'})
    with pytest.raises(RuntimeError,match='geometry_issues'):
        init_stage.validate_mpas_init(tmp_path,'2025-08-31T18:00:00Z')
    import json
    report=json.loads((tmp_path/'mpas-init-validation.json').read_text())
    assert report['valid'] is False
    assert any('zgrid' in issue for issue in report['geometry_issues'])


def test_configure_invariant_grid_preserves_state_and_comments(tmp_path, monkeypatch):
    import runpy,sys,yaml
    from pathlib import Path
    from types import SimpleNamespace
    module=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/reuse_invariant_vertical_grid.py'))
    namelist=tmp_path/'namelist.in';namelist.write_text('! preserve comment\nconfig_vertical_grid = .true.\n')
    invariant=tmp_path/'invariant.nc';invariant.write_bytes(b'invariant')
    state=tmp_path/'state.nc';state.write_bytes(b'previous scientific state')
    config={'links':[{'source':str(invariant),'target':'x1.10242.static.nc'}],
            'templates':[{'source':str(namelist),'target':'namelist.init_atmosphere'}],
            'validation':{'required_log_markers':[],'required_outputs':[str(state)]}}
    path=tmp_path/'mpas_init.yaml';path.write_text(yaml.safe_dump({'mpas_init':config},sort_keys=False))
    g=module['main'].__globals__
    monkeypatch.setitem(g,'load_campaign_spec',lambda _:SimpleNamespace(start_cycle='2025-09-01T00:00:00Z',cycle_interval_hours=6,initial_mpas_case=tmp_path,destination=tmp_path/'absent'))
    monkeypatch.setitem(g,'_load',lambda *_:SimpleNamespace(config_dir=tmp_path,context={},config=yaml.safe_load(path.read_text())['mpas_init']))
    monkeypatch.setattr(sys,'argv',['script','campaign.yaml'])
    module['main']();module['main']()
    assert namelist.read_text()=='! preserve comment\nconfig_vertical_grid = .false.\n'
    assert (tmp_path/'before-invariant-grid/state.nc').read_bytes()==b'previous scientific state'
    assert state.read_bytes()==b'previous scientific state'
    assert yaml.safe_load(path.read_text())['mpas_init']['validation']['geometry_reference']==str(invariant)
