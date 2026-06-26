from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPOSITORY_ROOT / "scripts" / "obs2ioda" / "run_prepbufr.sh"


def _make_fake_converter(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "test -r prepbufr.bufr\n"
        "printf 'ioda' > sfc_obs_2018041500.h5\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | os.stat_result((0,) * 10).st_mode | 0o111)


def test_prepbufr_runner_stages_fixed_basename_and_runs_converter(tmp_path: Path) -> None:
    input_file = tmp_path / "source.prepbufr"
    input_file.write_bytes(b"prepbufr")
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

    assert result.returncode == 0, result.stderr
    assert (work_dir / "prepbufr.bufr").is_symlink()
    assert (work_dir / "prepbufr.bufr").resolve() == input_file.resolve()
    assert (work_dir / "sfc_obs_2018041500.h5").read_bytes() == b"ioda"


def test_prepbufr_runner_refuses_unexpected_existing_basename(tmp_path: Path) -> None:
    input_file = tmp_path / "source.prepbufr"
    input_file.write_bytes(b"prepbufr")
    converter = tmp_path / "fake_obs2ioda"
    _make_fake_converter(converter)
    work_dir = tmp_path / "cycle"
    work_dir.mkdir()
    (work_dir / "prepbufr.bufr").write_text("unexpected", encoding="utf-8")

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
