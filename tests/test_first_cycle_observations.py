from pathlib import Path
from types import SimpleNamespace

import pytest

from monan_jedi_workflow import cli_frontend, obs_acquisition


def _spec(tmp_path):
    return SimpleNamespace(start_cycle='2025-09-01T00:00:00Z',
                           end_cycle='2025-09-01T06:00:00Z',
                           cycle_interval_hours=6,
                           obs2ioda_config=tmp_path / 'obs2ioda.yaml')


def test_acquisition_requires_missing_first_cycle_input(tmp_path, monkeypatch):
    monkeypatch.setattr(obs_acquisition, 'load_campaign_spec', lambda _: _spec(tmp_path))
    monkeypatch.setattr(obs_acquisition, '_acquisition_config', lambda _: {})
    def load_run(root, cycle):
        return SimpleNamespace(cycle=SimpleNamespace(cycle_time=cycle))
    monkeypatch.setattr(obs_acquisition, 'load_obs2ioda_run', load_run)
    def plan(run):
        first = run.cycle.cycle_time.endswith('00:00:00Z')
        filename = tmp_path / ('missing-first.bufr' if first else 'available-next.bufr')
        return {'converters': [{'name': 'prepbufr-conventional', 'inputs': [str(filename)]}]}
    (tmp_path / 'available-next.bufr').write_bytes(b'BUFR')
    monkeypatch.setattr(obs_acquisition, '_build_plan', plan)
    monkeypatch.setattr(obs_acquisition, 'cycle_candidate', lambda path, cycle: (path, False))
    monkeypatch.setattr(obs_acquisition, 'find_local_cycle_input', lambda *args: None)
    with pytest.raises(obs_acquisition.ObservationInputError, match='2025-09-01T00:00:00Z'):
        obs_acquisition.acquire_campaign_observations(tmp_path / 'campaign.yaml')


def test_campaign_check_rejects_missing_first_cycle_input(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_frontend, 'load_campaign_spec', lambda _: _spec(tmp_path))
    def check(root, cycle):
        if cycle.endswith('00:00:00Z'):
            raise obs_acquisition.ObservationInputError('Missing first cycle')
        return []
    monkeypatch.setattr(cli_frontend, 'check_obs_cycle_sources', check)
    with pytest.raises(obs_acquisition.ObservationInputError, match='Missing first cycle'):
        cli_frontend._check_observations(tmp_path / 'campaign.yaml')
