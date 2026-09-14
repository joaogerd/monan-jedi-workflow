from __future__ import annotations

import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from monan_jedi_workflow import obs_acquisition


def test_download_falls_back_to_curl_without_disabling_tls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "prepbufr.bufr"

    def fail_python(*args, **kwargs):
        raise urllib.error.URLError("CERTIFICATE_VERIFY_FAILED")

    monkeypatch.setattr(obs_acquisition, "_urllib_download", fail_python)

    def fake_which(name: str) -> str | None:
        if name == "curl":
            return "/usr/bin/curl"
        return None

    monkeypatch.setattr(obs_acquisition.shutil, "which", fake_which)

    def fake_run(command, **kwargs):
        assert "--insecure" not in command
        assert "-k" not in command
        output = Path(command[command.index("--output") + 1])
        output.write_bytes(b"cycle-correct-observation")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(obs_acquisition.subprocess, "run", fake_run)

    size, transport = obs_acquisition._download(
        "https://example.invalid/prepbufr.bufr", destination, timeout=30
    )

    assert transport == "curl-https"
    assert size == len(b"cycle-correct-observation")
    assert destination.read_bytes() == b"cycle-correct-observation"


def test_download_reports_all_secure_transport_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "prepbufr.bufr"

    def fail_python(*args, **kwargs):
        raise urllib.error.URLError("CERTIFICATE_VERIFY_FAILED")

    monkeypatch.setattr(obs_acquisition, "_urllib_download", fail_python)
    monkeypatch.setattr(obs_acquisition.shutil, "which", lambda name: None)

    with pytest.raises(obs_acquisition.ObservationInputError) as error:
        obs_acquisition._download(
            "https://example.invalid/prepbufr.bufr", destination, timeout=30
        )

    message = str(error.value)
    assert "TLS verification enabled" in message
    assert "curl: unavailable" in message
    assert "wget: unavailable" in message
    assert "TLS verification was not disabled" in message
