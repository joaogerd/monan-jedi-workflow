"""Local tests for the side-effect-free cyclic doctor command."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.doctor import (
    DoctorConfigError,
    format_doctor_report,
    run_doctor,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_config(
    path: Path,
    checks: list[dict[str, object]],
    *,
    temporal: bool = False,
    run_tasks: int | None = None,
) -> Path:
    config: dict[str, object] = {"doctor": {"checks": checks}}
    if temporal:
        config.update(
            {
                "cycle": {
                    "start": "2018-04-15T00:00:00Z",
                    "end": "2018-04-15T06:00:00Z",
                    "interval_hours": 6,
                },
                "assimilation": {
                    "method": "3dvar_fgat",
                    "fgat": {"trajectory_offsets_hours": [-3, 0, 3]},
                },
            }
        )
    if run_tasks is not None:
        config["run"] = {"tasks": run_tasks}
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def snapshot_tree(root: Path) -> dict[Path, tuple[int, int, int]]:
    return {
        path.relative_to(root): (
            path.stat().st_mode,
            path.stat().st_mtime_ns,
            path.stat().st_size,
        )
        for path in sorted(root.rglob("*"))
    }


def test_doctor_accepts_existing_regular_file(tmp_path: Path) -> None:
    resource = tmp_path / "B.nc"
    resource.write_text("metadata", encoding="utf-8")
    config = write_config(
        tmp_path / "doctor.yaml",
        [{"name": "B matrix", "path": "B.nc", "kind": "file"}],
    )

    report = run_doctor(config)

    assert report.ok
    assert report.passed == 1
    assert report.results[0].path == resource
    assert "[OK] B matrix [file]" in format_doctor_report(report)


def test_doctor_reports_missing_file_without_creating_it(tmp_path: Path) -> None:
    missing = tmp_path / "missing.nc"
    config = write_config(
        tmp_path / "doctor.yaml",
        [{"name": "B matrix", "path": "missing.nc", "kind": "file"}],
    )

    report = run_doctor(config)

    assert not report.ok
    assert report.failed == 1
    assert report.results[0].detail == "missing"
    assert not missing.exists()


def test_doctor_accepts_existing_directory(tmp_path: Path) -> None:
    physics = tmp_path / "physics"
    physics.mkdir()
    config = write_config(
        tmp_path / "doctor.yaml",
        [{"name": "physics", "path": "physics", "kind": "directory"}],
    )

    report = run_doctor(config)

    assert report.ok
    assert report.results[0].detail == "directory"


def test_doctor_distinguishes_executable_present_and_missing(tmp_path: Path) -> None:
    executable = tmp_path / "mpasjedi_variational.x"
    executable.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    config = write_config(
        tmp_path / "doctor.yaml",
        [
            {
                "name": "MPAS-JEDI",
                "path": "mpasjedi_variational.x",
                "kind": "executable",
            },
            {
                "name": "missing executable",
                "path": "missing.x",
                "kind": "executable",
            },
        ],
    )

    report = run_doctor(config)

    assert not report.ok
    assert [result.ok for result in report.results] == [True, False]
    assert report.results[0].detail == "executable file"
    assert report.results[1].detail == "missing"


def test_doctor_binds_partition_filename_to_declared_run_tasks(tmp_path: Path) -> None:
    partition = tmp_path / "x1.10242.graph.info.part.64"
    partition.write_text("partition", encoding="utf-8")
    config = write_config(
        tmp_path / "doctor.yaml",
        [
            {
                "name": "MPAS partition",
                "path": "x1.10242.graph.info.part.{tasks}",
                "kind": "file",
            }
        ],
        run_tasks=64,
    )

    report = run_doctor(config)

    assert report.ok
    assert report.results[0].path == partition


def test_doctor_fails_when_partition_for_declared_tasks_is_absent(tmp_path: Path) -> None:
    (tmp_path / "x1.10242.graph.info.part.64").write_text(
        "partition", encoding="utf-8"
    )
    config = write_config(
        tmp_path / "doctor.yaml",
        [
            {
                "name": "MPAS partition",
                "path": "x1.10242.graph.info.part.{tasks}",
                "kind": "file",
            }
        ],
        run_tasks=32,
    )

    report = run_doctor(config)

    assert not report.ok
    assert report.results[0].path.name == "x1.10242.graph.info.part.32"
    assert report.results[0].detail == "missing"


def test_doctor_reports_required_access_without_touching_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    physics = tmp_path / "physics"
    physics.mkdir()
    config = write_config(
        tmp_path / "doctor.yaml",
        [
            {
                "name": "physics",
                "path": "physics",
                "kind": "directory",
                "access": ["read", "write"],
            }
        ],
    )

    import monan_jedi_workflow.doctor as doctor

    real_access = doctor.os.access
    monkeypatch.setattr(
        doctor.os,
        "access",
        lambda path, mode: False if mode == os.W_OK else real_access(path, mode),
    )

    report = run_doctor(config)

    assert not report.ok
    assert report.results[0].detail == "missing write access"


def test_doctor_expands_trajectory_placeholders_for_each_planned_state(
    tmp_path: Path,
) -> None:
    expected = [
        tmp_path / "states" / f"2018041500.{stamp}.nc"
        for stamp in [
            "2018-04-14_21.00.00",
            "2018-04-15_00.00.00",
            "2018-04-15_03.00.00",
        ]
    ]
    (tmp_path / "states").mkdir()
    for path in expected:
        path.write_text("state", encoding="utf-8")
    config = write_config(
        tmp_path / "doctor.yaml",
        [
            {
                "name": "FGAT trajectory",
                "path": "states/{cycle_id}.{valid_mpas_time}.nc",
                "kind": "file",
                "scope": "trajectory",
            }
        ],
        temporal=True,
    )

    report = run_doctor(config)

    assert report.ok
    assert [result.path for result in report.results] == expected
    assert all(result.check.name == "FGAT trajectory" for result in report.results)


def test_doctor_rejects_invalid_yaml(tmp_path: Path) -> None:
    config = tmp_path / "doctor.yaml"
    config.write_text("doctor: [unterminated\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        run_doctor(config)


def test_doctor_rejects_unknown_path_placeholders(tmp_path: Path) -> None:
    config = write_config(
        tmp_path / "doctor.yaml",
        [{"name": "bad template", "path": "{unknown}.nc", "kind": "file"}],
    )

    with pytest.raises(DoctorConfigError, match="unknown placeholder"):
        run_doctor(config)


def test_doctor_does_not_modify_the_filesystem(tmp_path: Path) -> None:
    resource = tmp_path / "resource.nc"
    resource.write_text("contents", encoding="utf-8")
    config = write_config(
        tmp_path / "doctor.yaml",
        [
            {"name": "file", "path": "resource.nc", "kind": "file"},
            {"name": "missing", "path": "missing.nc", "kind": "file"},
        ],
    )
    before = snapshot_tree(tmp_path)

    report = run_doctor(config)

    assert not report.ok
    assert snapshot_tree(tmp_path) == before


def test_doctor_cli_integrates_multiple_local_resources(tmp_path: Path) -> None:
    (tmp_path / "physics").mkdir()
    (tmp_path / "B.nc").write_text("B", encoding="utf-8")
    executable = tmp_path / "mpasjedi_variational.x"
    executable.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    config = write_config(
        tmp_path / "doctor.yaml",
        [
            {
                "name": "MPAS-JEDI",
                "path": "mpasjedi_variational.x",
                "kind": "executable",
            },
            {"name": "B matrix", "path": "B.nc", "kind": "file"},
            {"name": "physics", "path": "physics", "kind": "directory"},
        ],
    )
    environment = os.environ | {"PYTHONPATH": str(REPO_ROOT)}

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/monan-jedi-cycle-doctor"),
            str(config),
        ],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "doctor: read-only verification" in completed.stdout
    assert "[OK] MPAS-JEDI [executable]" in completed.stdout
    assert "summary: 3 passed, 0 failed" in completed.stdout
