"""Observation acquisition runs before conversion preflight and never guesses dates."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from monan_jedi_workflow.input_acquisition import InputUnavailable
import monan_jedi_workflow.observation_acquisition as acquire
import monan_jedi_workflow.platform_backend as backend
import monan_jedi_workflow.obs2ioda_stage as obs


def _setup(tmp_path, monkeypatch, *, configured):
    raw = tmp_path / 'obs/2024/prepbufr.gdas.2024022900.nr'
    run = SimpleNamespace(context={'cycle_year': '2024',
                                   'cycle_yyyymmddhh': '2024022900'})
    op = SimpleNamespace(section={
        'acquisition': {'providers': (
            [{'converter': 'prepbufr-conventional',
              'url': 'https://example.invalid/{cycle_year}/{cycle_yyyymmddhh}.nr'}]
            if configured else []
        )},
    })
    request = SimpleNamespace(cycle='2024-02-29T00:00:00Z')
    monkeypatch.setattr(backend, 'materialize', lambda _op, d: d)
    monkeypatch.setattr(backend, 'render_run', lambda _op, _req, _dir: run)
    monkeypatch.setattr(obs, '_build_plan', lambda _run: {'converters': [{
        'name': 'prepbufr-conventional',
        'inputs': [str(raw), str(tmp_path / 'run_prepbufr.sh')],
    }]})
    return raw, op, request


def test_missing_observation_uses_declared_provider_only(tmp_path, monkeypatch):
    raw, op, request = _setup(tmp_path, monkeypatch, configured=True)
    seen = []
    def fake_ensure_input(**kwargs):
        seen.append(kwargs)
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b'BUFR fixture')
        return raw
    monkeypatch.setattr(acquire, 'ensure_input', fake_ensure_input)
    assert acquire.acquire_required_observations(op, request) == [raw]
    assert seen[0]['url'] == 'https://example.invalid/2024/2024022900.nr'
    assert seen[0]['target'] == raw
    # Download is only necessary for missing data.
    assert acquire.acquire_required_observations(op, request) == []
    assert len(seen) == 1


def test_missing_historical_provider_reports_exact_date(tmp_path, monkeypatch):
    raw, op, request = _setup(tmp_path, monkeypatch, configured=False)
    with pytest.raises(InputUnavailable, match='No URL provider configured') as error:
        acquire.acquire_required_observations(op, request)
    assert str(raw) in str(error.value)
    assert request.cycle in str(error.value)
    assert not raw.exists()


def test_existing_observations_work_without_provider(tmp_path, monkeypatch):
    raw, op, request = _setup(tmp_path, monkeypatch, configured=False)
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b'BUFR fixture')
    assert acquire.acquire_required_observations(op, request) == []
