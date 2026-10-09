from pathlib import Path
import time

from monan_jedi_workflow import obs_acquisition


def test_download_reports_start_progress_and_completion(tmp_path, monkeypatch, capsys):
    def transfer(url, temporary, **kwargs):
        assert '[DOWNLOAD]' in capsys.readouterr().out
        temporary.write_bytes(b'BUFR' * 1024)
        time.sleep(0.05)
    monkeypatch.setattr(obs_acquisition, '_urllib_download', transfer)
    monkeypatch.setattr(obs_acquisition, 'DOWNLOAD_PROGRESS_SECONDS', 0.01, raising=False)
    target = tmp_path / 'observations.bufr'
    size, transport = obs_acquisition._download('https://example.invalid/observations.bufr', target, timeout=30)
    output = capsys.readouterr().out
    assert '[PROGRESS]' in output
    assert '[DONE]' in output
    assert size == 4096
    assert transport == 'python-https'
    assert target.read_bytes().startswith(b'BUFR')


def test_download_reports_waiting_before_first_bytes(tmp_path, monkeypatch, capsys):
    def transfer(url, temporary, **kwargs):
        time.sleep(0.05)
        temporary.write_bytes(b'BUFR')
    monkeypatch.setattr(obs_acquisition, '_urllib_download', transfer)
    monkeypatch.setattr(obs_acquisition, 'DOWNLOAD_PROGRESS_SECONDS', 0.01, raising=False)
    obs_acquisition._download('https://example.invalid/obs', tmp_path / 'obs', timeout=30)
    assert 'aguardando' in capsys.readouterr().out
