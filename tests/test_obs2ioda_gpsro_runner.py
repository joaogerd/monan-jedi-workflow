from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPOSITORY_ROOT / "scripts" / "obs2ioda" / "run_gpsro.sh"


def _make_fake_converter(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "test \"$1\" = gdas.gpsro.t00z.20180415.bufr\n"
        "test -r \"$1\"\n"
        "printf 'ioda' > gnssro_obs_2018041500.h5\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | os.stat_result((0,) * 10).st_mode | 0o111)


def test_gpsro_runner_stages_input_basename_and_runs_converter(tmp_path: Path) -> None:
    input_file = tmp_path / "gdas.gpsro.t00z.20180415.bufr"
    input_file.write_bytes(b"gpsro")
    converter = tmp_path / "fake_obs2ioda"
    _make_fake_converter(converter)
    work_dir = tmp_path / "cycle"
    work_dir.mkdir()

    result = subprocess.run(
        [
            "bash",
            str(RUNNER),
            "--executable",
            str(converter),
            "--input",
            str(input_file),
        ],
        cwd=work_dir,
        text=True,
        capture_output=True,
        check=False,
    )

    staged = work_dir / input_file.name
    assert result.returncode == 0, result.stderr
    assert staged.is_symlink()
    assert staged.resolve() == input_file.resolve()
    assert (work_dir / "gnssro_obs_2018041500.h5").read_bytes() == b"ioda"


def test_gpsro_runner_refuses_unexpected_existing_basename(tmp_path: Path) -> None:
    input_file = tmp_path / "raw" / "gdas.gpsro.t00z.20180415.bufr"
    input_file.parent.mkdir()
    input_file.write_bytes(b"gpsro")
    converter = tmp_path / "fake_obs2ioda"
    _make_fake_converter(converter)
    work_dir = tmp_path / "cycle"
    work_dir.mkdir()
    (work_dir / input_file.name).write_text("unexpected", encoding="utf-8")

    result = subprocess.run(
        [
            "bash",
            str(RUNNER),
            "--executable",
            str(converter),
            "--input",
            str(input_file),
        ],
        cwd=work_dir,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "refusing to replace" in result.stderr
