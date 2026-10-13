from pathlib import Path

from monan_jedi_workflow.obs2ioda_stage import load_obs2ioda_run


def test_reference_observation_paths_render_for_first_and_last_cycle(monkeypatch):
    monkeypatch.setenv('MONAN_JEDI_INSTALL_ROOT', '/test/runtime')
    monkeypatch.setenv('USER', 'testuser')
    root = Path(__file__).resolve().parents[1] / 'examples/case'
    for cycle, day, hour in [('2025-09-01T00:00:00Z', '20250901', '00'),
                             ('2025-09-08T00:00:00Z', '20250908', '00'),
                             ('2025-09-01T18:00:00Z', '20250901', '18')]:
        run = load_obs2ioda_run(root, cycle)
        assert run.context['gpsro_input'].endswith(f'/2025/gdas.gpsro.t{hour}z.{day}.bufr')
        assert run.context['prepbufr_input'].endswith(f'/2025/prepbufr.gdas.{day}.t{hour}z.nr.48h')


def test_reference_header_requirements_match_observer_filters(monkeypatch):
    from monan_jedi_workflow.obs2ioda_stage import _render_inspection
    monkeypatch.setenv('MONAN_JEDI_INSTALL_ROOT', '/test/runtime')
    monkeypatch.setenv('USER', 'testuser')
    root = Path(__file__).resolve().parents[1] / 'examples/case'
    run = load_obs2ioda_run(root, '2025-09-01T00:00:00Z')
    converters = {item['name']: item for item in run.config['converters']}
    conventional = _render_inspection(run, converters['prepbufr-conventional'], Path('/test/sondes.h5'))
    gpsro = _render_inspection(run, converters['gpsro-gnssro'], Path('/test/gnssro.h5'))
    assert 'PreQC' in conventional['required_header_markers']
    assert gpsro['required_header_markers'] == ['MetaData', 'ObsValue', 'ObsError']
