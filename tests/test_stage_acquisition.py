from pathlib import Path
from types import SimpleNamespace

from monan_jedi_workflow import cli_frontend, obs_acquisition, obs_cycle_stage, wps_stage


def test_campaign_create_run_check_do_not_download(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_frontend, '_fetch_observations', lambda *_: (_ for _ in ()).throw(AssertionError('global acquisition')))
    monkeypatch.setattr(cli_frontend, '_check_observations', lambda *_: (_ for _ in ()).throw(AssertionError('global input requirement')))
    monkeypatch.setattr(cli_frontend.cli_extended, 'main', lambda args: 0)
    for action in ('create', 'run', 'check'):
        assert cli_frontend._dispatch(['campaign', action, str(tmp_path / 'campaign.yaml')]) == 0


def test_cycle_acquisition_only_loads_requested_cycle(tmp_path, monkeypatch):
    (tmp_path / 'profile.yaml').write_text('profile: {}\n')
    calls = []
    monkeypatch.setattr(obs_acquisition, 'load_obs2ioda_run', lambda root, cycle: calls.append(cycle) or SimpleNamespace(cycle=cycle))
    monkeypatch.setattr(obs_acquisition, '_build_plan', lambda _: {'converters': []})
    obs_acquisition.acquire_cycle_observations(tmp_path, '2025-09-01T06:00:00Z')
    assert calls == ['2025-09-01T06:00:00Z']


def test_doctor_acquires_before_checking_inputs(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(obs_cycle_stage, 'acquire_cycle_observations', lambda *args: calls.append('acquire'))
    monkeypatch.setattr(obs_cycle_stage, 'check_obs_cycle_sources', lambda *args: calls.append('check') or [])
    monkeypatch.setattr(obs_cycle_stage, 'doctor_obs2ioda', lambda *args: calls.append('doctor'))
    obs_cycle_stage.doctor_obs2ioda_resolved(tmp_path, '2025-09-01T00:00:00Z')
    assert calls == ['acquire', 'check', 'doctor']


def test_wps_fetches_declared_missing_grib_and_reuses_local(tmp_path, monkeypatch):
    target = tmp_path / 'gfs.grib2'
    run = SimpleNamespace(config={'acquisition': {'source': str(target), 'url': 'https://example.invalid/gfs.{cycle_hour}'}},
                          context={'cycle_hour': '18'}, config_dir=tmp_path)
    calls = []
    def download(url, destination, **kwargs):
        calls.append(url)
        destination.write_bytes(b'GRIBdata')
        return (8, 'test')
    monkeypatch.setattr(obs_acquisition, '_download', download)
    wps_stage.acquire_wps_input(run)
    wps_stage.acquire_wps_input(run)
    assert calls == ['https://example.invalid/gfs.18']
    assert target.read_bytes() == b'GRIBdata'


def test_preflight_defers_downloadable_inputs_without_fetching(tmp_path, monkeypatch):
    from monan_jedi_workflow import campaign
    from monan_jedi_workflow.campaign import CampaignSpec, PreflightItem
    obs = tmp_path / 'obs2ioda.yaml'
    obs.write_text('obs2ioda: {}\n')
    config = tmp_path / 'campaign.yaml'
    config.write_text('profile:\n  observation_acquisition:\n    enabled: true\n    providers:\n      prep:\n        type: https\n        url: https://example.invalid/obs\n')
    spec = CampaignSpec(config_path=config, name='test', start_cycle='2025-09-01T00:00:00Z',
                        end_cycle='2025-09-01T06:00:00Z', duration_hours=6, destination=tmp_path/'run',
                        cycling_jedi_case=tmp_path, initial_mpas_case=tmp_path, mpas_case=tmp_path,
                        obs2ioda_config=obs, swf_command=('swf',))
    missing = tmp_path / 'missing.bufr'
    monkeypatch.setattr(campaign, '_configuration_placeholders', lambda _: PreflightItem('config', True, 'ok'))
    monkeypatch.setattr(campaign, '_initial_mpas_detail', lambda _: PreflightItem('init', True, 'ok'))
    monkeypatch.setattr(campaign, '_command_available', lambda _: True)
    monkeypatch.setattr(campaign, '_rendered_obs_inputs', lambda *_: ([missing], []))
    monkeypatch.setattr(campaign, 'load_obs2ioda_run', lambda *_: None)
    monkeypatch.setattr(campaign, '_build_plan', lambda _: {'converters': [{'name': 'prep', 'inputs': [str(missing)]}]})
    monkeypatch.setattr(obs_acquisition, '_download', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('preflight downloaded')))
    report = campaign.preflight_campaign(spec)
    assert report.valid
    assert not missing.exists()
    assert any('acquisition will run per cycle' in item.detail for item in report.items)


def test_existing_case_upgrade_preserves_comments_and_scientific_values(tmp_path, monkeypatch):
    import runpy
    import sys
    script = Path(__file__).resolve().parents[1] / 'scripts/configure_gfs_acquisition.py'
    module = runpy.run_path(str(script))
    source = tmp_path / 'source'
    source.mkdir()
    destination = tmp_path / 'campaign'
    (destination / 'initialization').mkdir(parents=True)
    original = '# keep my comment\nwps:\n  variables:\n    gfs_file: /data/custom/gfs.grib\n  work_dir: work/wps\n'
    paths = [source / 'wps.yaml', destination / 'initialization/wps.yaml']
    for path in paths:
        path.write_text(original)
    monkeypatch.setitem(module['main'].__globals__, 'load_campaign_spec', lambda _: SimpleNamespace(initial_mpas_case=source, destination=destination))
    monkeypatch.setattr(sys, 'argv', ['configure_gfs_acquisition.py', str(tmp_path/'campaign.yaml')])
    module['main']()
    module['main']()
    for path in paths:
        assert path.read_text().startswith('# keep my comment\n')
        assert 'gfs_file: /data/custom/gfs.grib' in path.read_text()
        assert path.with_name(path.name+'.before-acquisition').read_text() == original
