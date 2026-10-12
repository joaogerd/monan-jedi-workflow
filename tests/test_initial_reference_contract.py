from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

ROOT = Path(__file__).resolve().parents[1] / 'examples/case'


def test_initial_forecast_preserves_m3_stream_contract():
    streams = ET.fromstring((ROOT/'templates/streams.atmosphere.initial.in').read_text())
    names = {entry.attrib['name']: entry.attrib for entry in streams}
    assert names['diagnostics']['type'] == 'none'
    assert names['restart']['output_interval'] == '24:00:00'
    assert names['da_state']['output_interval'] == '03:00:00'
    assert names['input']['filename_template'].startswith('mpas.init.')


def test_initial_forecast_preserves_m3_explicit_diffusion_and_table_endian():
    text = (ROOT/'templates/namelist.atmosphere.initial.in').read_text()
    for name in ('h_mom_eddy_visc2','h_mom_eddy_visc4','v_mom_eddy_visc2','h_theta_eddy_visc2','h_theta_eddy_visc4','v_theta_eddy_visc2'):
        assert f'config_{name} = 0.0' in text
    assert 'config_dt = 1200' in text
    config = yaml.safe_load((ROOT/'initialization/mpas.yaml').read_text())
    assert config['mpas']['pbs']['environment']['GFORTRAN_CONVERT_UNIT'] == 'big_endian:101-200'


def test_restore_script_updates_declared_templates_and_keeps_backups(tmp_path, monkeypatch):
    import runpy
    import sys
    from types import SimpleNamespace
    from datetime import datetime, timezone
    script = ROOT.parents[1]/'scripts/restore_initial_mpas_reference.py'
    module = runpy.run_path(str(script))
    config = tmp_path/'initialization'
    config.mkdir()
    yaml_path = config/'mpas.yaml'
    original = 'mpas:\n  pbs:\n    environment:\n      OMP_NUM_THREADS: "1"\n'
    yaml_path.write_text(original)
    template = config/'namelist.atmosphere.initial.in'
    template.write_text('old template\n')
    spec = SimpleNamespace(start_cycle='2025-09-01T00:00:00Z', cycle_interval_hours=6,
                           initial_mpas_case=config, destination=tmp_path/'absent')
    globals_ = module['main'].__globals__
    monkeypatch.setitem(globals_, 'load_campaign_spec', lambda _: spec)
    monkeypatch.setitem(globals_, 'load_mpas_run', lambda *_: SimpleNamespace(config_dir=config, context={},
                        config={'templates': [{'target':'namelist.atmosphere','source':str(template)}],
                                'pbs': {'environment': {}}}))
    monkeypatch.setattr(sys,'argv',['script','campaign.yaml'])
    module['main']()
    assert template.read_text()==(ROOT/'templates/namelist.atmosphere.initial.in').read_text()
    assert yaml.safe_load(yaml_path.read_text())['mpas']['pbs']['environment']['GFORTRAN_CONVERT_UNIT']=='big_endian:101-200'
    assert yaml_path.with_name('mpas.yaml.before-m3-initial').read_text()==original
    assert template.with_name(template.name+'.before-m3-initial').read_text()=='old template\n'
