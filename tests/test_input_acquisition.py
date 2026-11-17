"""On-demand scientific input acquisition never publishes incomplete data."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest

from monan_jedi_workflow.input_acquisition import ensure_input, InputUnavailable


class _Response(BytesIO):
    def __init__(self, data, status=200, length=None):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Length": str(len(data) if length is None else length)}


def test_missing_grib_is_downloaded_once_and_reused(tmp_path, monkeypatch):
    destination = tmp_path / "gfs/2024022818/gfs.t18z.pgrb2.0p25.f000"
    called = []
    def fetch(url, timeout):
        called.append((url, timeout))
        return _Response(b"GRIB" + b"x" * 64)
    monkeypatch.setattr("monan_jedi_workflow.input_acquisition.urllib.request.urlopen", fetch)
    url = "https://example.invalid/date/gfs.t18z.pgrb2.0p25.f000"
    assert ensure_input(target=destination, url=url, label="GFS", magic=b"GRIB") == destination
    assert destination.read_bytes().startswith(b"GRIB")
    assert ensure_input(target=destination, url=url, label="GFS", magic=b"GRIB") == destination
    assert called == [(url, 300)]
    assert not list(destination.parent.glob(".acquiring-*"))


def test_rejects_html_404_and_incomplete_download_without_publishing(tmp_path, monkeypatch):
    target = tmp_path / "data.grib2"
    monkeypatch.setattr(
        "monan_jedi_workflow.input_acquisition.urllib.request.urlopen",
        lambda *a, **kw: _Response(b"<html>not GRIB</html>"),
    )
    with pytest.raises(InputUnavailable, match="signature"):
        ensure_input(target=target, url="https://example.invalid/a", label="GFS", magic=b"GRIB")
    assert not target.exists()
    monkeypatch.setattr(
        "monan_jedi_workflow.input_acquisition.urllib.request.urlopen",
        lambda *a, **kw: _Response(b"GRIB", length=500),
    )
    with pytest.raises(InputUnavailable, match="incomplete"):
        ensure_input(target=target, url="https://example.invalid/a", label="GFS", magic=b"GRIB")
    assert not target.exists()


def test_no_provider_has_actionable_error_and_preserves_existing(tmp_path):
    target = tmp_path / "obs_20240229.bufr"
    with pytest.raises(InputUnavailable, match="No downloadable provider"):
        ensure_input(target=target, url=None, label="PREPNR 2024")
    target.write_bytes(b"existing bytes")
    assert ensure_input(target=target, url=None, label="PREPNR 2024") == target


def test_wps_prepare_acquires_missing_gfs_before_linking(tmp_path, monkeypatch):
    from monan_jedi_workflow.wps_stage import prepare_wps
    from monan_jedi_workflow.experiment_start import create_experiment
    monkeypatch.setenv("MONAN_GFS_ROOT", str(tmp_path / "gfs"))
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", str(tmp_path / "install"))
    root = tmp_path / "case"
    create_experiment(root, start="2024-02-29T00:00:00Z")
    # Simulate the provider and WPS executables with local fixtures; there
    # is no network or HPC dependency in this regression test.
    install = tmp_path / "install"
    (install / "bin").mkdir(parents=True)
    (install / "share/wps/Variable_Tables").mkdir(parents=True)
    for executable in ("link_grib.csh", "ungrib.exe"):
        (install / "bin" / executable).write_text("tool")
    (install / "share/wps/Variable_Tables/Vtable.GFS").write_text("vtable")
    fetched = []
    def fetch(url, timeout):
        fetched.append(url)
        return _Response(b"GRIB" + b"test")
    monkeypatch.setattr("monan_jedi_workflow.input_acquisition.urllib.request.urlopen", fetch)
    run = prepare_wps(root / "science/initialization", "2024-02-28T18:00:00Z")
    assert (run.work_dir / "gfs.input.grib2").is_symlink()
    assert "gfs.20240228/18" in fetched[0]
    assert len(fetched) == 1
