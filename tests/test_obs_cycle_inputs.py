from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from monan_jedi_workflow.obs_cycle_inputs import cycle_candidate, resolve_cycle_input


def cycle(iso="2026-01-31T00:00:00Z"):
    return SimpleNamespace(
        value=datetime.fromisoformat(iso.replace("Z", "+00:00")),
        cycle_time=iso,
    )


def test_runner_not_interpreted_as_cycle_dated_input():
    path = Path("/p/experiments/m3-7dias-20260130/science/runners/run_prepbufr.sh")
    assert cycle_candidate(path, cycle()) == (path, False)


def test_correct_observation_filename_ignores_campaign_directory_date(tmp_path):
    target = tmp_path / "m3-7dias-20260130/observations/prepnr/2026/prepbufr.gdas.2026013100.nr"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"PREPBUFR")
    assert cycle_candidate(target, cycle()) == (target, False)
    assert resolve_cycle_input(target, cycle(), "prepbufr-conventional")[0] == target


def test_wrong_dated_observation_changes_only_basename(tmp_path):
    source = tmp_path / "m3-7dias-20260130/prepbufr.gdas.2026013000.nr"
    expected = source.with_name("prepbufr.gdas.2026013100.nr")
    assert cycle_candidate(source, cycle()) == (expected, True)


def test_gpsro_date_and_hour_in_filename_keep_parent_unchanged():
    source = Path("/p/experiments/m3-7dias-20260130/gdas.gpsro.t18z.20260130.bufr")
    candidate, changed = cycle_candidate(source, cycle())
    assert changed
    assert candidate.parent == source.parent
    assert candidate.name == "gdas.gpsro.t00z.20260131.bufr"
