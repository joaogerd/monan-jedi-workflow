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
