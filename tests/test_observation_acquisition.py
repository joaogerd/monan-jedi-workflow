"""Regression tests for the restored, date-safe historical GDEX acquisition."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from monan_jedi_workflow.cycle_context import parse_cycle_time
from monan_jedi_workflow.input_acquisition import InputUnavailable
import monan_jedi_workflow.observation_acquisition as acquire
import monan_jedi_workflow.obs_acquisition as legacy
import monan_jedi_workflow.platform_backend as backend
import monan_jedi_workflow.obs2ioda_stage as obs


def setup_case(tmp_path, monkeypatch, *, config=None):
    cycle = parse_cycle_time("2024-02-29T00:00:00Z")
    raw_pre = tmp_path / "obs/2024/prepbufr.gdas.2024022900.nr"
    raw_gps = tmp_path / "obs/2024/gdas.gpsro.t00z.20240229.bufr"
    run = SimpleNamespace(cycle=cycle)
    op = SimpleNamespace(section={"acquisition": config or {"providers": []}})
    request = SimpleNamespace(cycle=cycle.cycle_time)
    monkeypatch.setattr(backend, "materialize", lambda _op, directory: directory)
    monkeypatch.setattr(backend, "render_run", lambda _op, _req, _dir: run)
    monkeypatch.setattr(obs, "_build_plan", lambda _run: {"converters": [
        {"name": "prepbufr-conventional", "inputs": [
            str(raw_pre), str(tmp_path / "run_prepbufr.sh")
        ]},
        {"name": "gpsro-gnssro", "inputs": [
            str(raw_gps), str(tmp_path / "run_gpsro.sh")
        ]},
    ]})
    return raw_pre, raw_gps, op, request


def test_previous_gdex_provider_is_restored_for_both_products(tmp_path, monkeypatch):
    raw_pre, raw_gps, op, request = setup_case(tmp_path, monkeypatch)
    seen = []

    def mock_download(path, cycle, converter, provider):
        seen.append((converter, provider["type"], provider["url"], provider.get("member")))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"BUFR" + b"x" * 32)
        return SimpleNamespace(destination=str(path))

    monkeypatch.setattr(legacy, "_acquire_remote", mock_download)
    assert acquire.acquire_required_observations(op, request) == [raw_pre, raw_gps]
    assert seen[0][0:2] == ("prepbufr-conventional", "https")
    assert "/d337000/prep48h/" in seen[0][2]
    assert seen[1][0:2] == ("gpsro-gnssro", "https-tar")
    assert "/d735000/gpsro/" in seen[1][2]
    assert "gdas.gpsro.t{cycle_hour}z." in seen[1][3]
    # Both products remain cached, no new remote operations.
    assert acquire.acquire_required_observations(op, request) == []
    assert len(seen) == 2


def test_opt_out_is_explicit_and_never_downloads(tmp_path, monkeypatch):
    raw_pre, _, op, request = setup_case(
        tmp_path, monkeypatch, config={"enabled": False}
    )
    monkeypatch.setattr(legacy, "_acquire_remote",
                        lambda *a: pytest.fail("download should be disabled"))
    with pytest.raises(InputUnavailable, match="No acquisition provider"):
        acquire.acquire_required_observations(op, request)
    assert not raw_pre.exists()


def test_existing_data_reused_without_remote_access(tmp_path, monkeypatch):
    raw_pre, raw_gps, op, request = setup_case(tmp_path, monkeypatch)
    for path in (raw_pre, raw_gps):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"BUFR existing")
    monkeypatch.setattr(legacy, "_acquire_remote",
                        lambda *a: pytest.fail("should not download existing observations"))
    assert acquire.acquire_required_observations(op, request) == []


def test_custom_provider_overrides_default_without_fabricating(tmp_path, monkeypatch):
    _, _, op, request = setup_case(tmp_path, monkeypatch, config={
        "providers": [{"converter": "prepbufr-conventional",
                       "type": "https",
                       "url": "https://archive.example.org/{cycle_yyyymmddhh}.nr"}],
    })
    seen = []
    def mock_download(path, cycle, converter, provider):
        seen.append(provider["url"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"BUFR fixture")
    monkeypatch.setattr(legacy, "_acquire_remote", mock_download)
    acquire.acquire_required_observations(op, request)
    assert seen[0].startswith("https://archive.example.org/")
    assert "/d735000/gpsro/" in seen[1]



def test_historical_gdex_provider_switches_with_year():
    from monan_jedi_workflow.cycle_context import parse_cycle_time
    prior = acquire._default_provider(
        "prepbufr-conventional", parse_cycle_time("2024-02-29T00:00:00Z")
    )
    recent = acquire._default_provider(
        "prepbufr-conventional", parse_cycle_time("2025-09-01T00:00:00Z")
    )
    assert prior["product"] == "PREP48H"
    assert "t{cycle_hour}z.nr.48h" in prior["url"]
    assert recent["product"] == "PREPNR"
    assert "prepbufr.gdas.{cycle_yyyymmddhh}.nr" in recent["url"]



def test_leap_day_provider_renders_only_requested_cycle():
    from monan_jedi_workflow.cycle_context import parse_cycle_time
    from monan_jedi_workflow.obs_acquisition import _render
    cycle = parse_cycle_time("2024-02-29T06:00:00Z")
    pre = acquire._default_provider("prepbufr-conventional", cycle)
    gps = acquire._default_provider("gpsro-gnssro", cycle)
    assert _render(pre["url"], cycle) == (
        "https://data.gdex.ucar.edu/d337000/prep48h/2024/"
        "prepbufr.gdas.20240229.t06z.nr.48h"
    )
    assert _render(gps["url"], cycle) == (
        "https://data.gdex.ucar.edu/d735000/gpsro/2024/gpsro.20240229.tar.gz"
    )
    assert _render(gps["member"], cycle) == (
        "gdas.gpsro.t06z.20240229.bufr"
    )
