from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.obs2ioda_stage import (
    Obs2IODADoctorError,
    Obs2IODAValidationError,
    doctor_obs2ioda,
    prepare_obs2ioda,
    run_obs2ioda,
    validate_obs2ioda,
)


CYCLE = "2018-04-15T00:00:00Z"


def write_config(tmp_path: Path, *, markers: list[str] | None = None) -> Path:
    config_dir = tmp_path / "experiment"
    (config_dir / "inputs").mkdir(parents=True)
    (config_dir / "inputs" / "20180415T000000Z.bufr").write_bytes(b"bufr")
    header = "MetaData\nObsValue\nObsError\nPreQC"
    content = {
        "obs2ioda": {
            "variables": {
                "converter_python": sys.executable,
                "input_root": "inputs",
                "output_root": "work/obs2ioda",
            },
            "work_dir": "{output_root}/{cycle_id}",
            "provenance": {"sha256": True},
            "probes": [
                {
                    "name": "converter-interface",
                    "argv": ["{converter_python}", "-c", "print('probe-ok')"],
                    "required_output_markers": ["probe-ok"],
                }
            ],
            "inspection": {
                "argv": ["{converter_python}", "-c", f"print({header!r})", "{output}"],
                "required_header_markers": markers or ["MetaData", "ObsValue", "ObsError", "PreQC"],
                "timeout_seconds": 10,
            },
            "converters": [
                {
                    "name": "sample",
                    "inputs": ["{input_root}/{cycle_id}.bufr"],
                    "outputs": ["{work_dir}/sample.nc4"],
                    "argv": [
                        "{converter_python}",
                        "-c",
                        "from pathlib import Path; Path(r'{work_dir}/sample.nc4').write_bytes(b'ioda')",
                    ],
                }
            ],
        }
    }
    (config_dir / "obs2ioda.yaml").write_text(yaml.safe_dump(content), encoding="utf-8")
    return config_dir


def test_operational_obs2ioda_records_provenance_and_validates(tmp_path: Path) -> None:
    config_dir = write_config(tmp_path)

    doctor = json.loads(doctor_obs2ioda(config_dir, CYCLE).read_text())
    assert doctor["valid"] is True
    assert doctor["probes"][0]["valid"] is True

    run = prepare_obs2ioda(config_dir, CYCLE)
    manifest = json.loads(run.manifest_path.read_text())
    assert manifest["input_records"]["sample"][0]["sha256"]
    assert manifest["plan_sha256"]
    assert manifest["converters"][0]["argv"][0] == sys.executable

    run_obs2ioda(config_dir, CYCLE)
    report = json.loads(validate_obs2ioda(config_dir, CYCLE).read_text())
    assert report["valid"] is True
    assert report["records"][0]["missing_header_markers"] == []


def test_obs2ioda_validation_rejects_missing_header_marker(tmp_path: Path) -> None:
    config_dir = write_config(tmp_path, markers=["MetaData", "NonexistentGroup"])
    prepare_obs2ioda(config_dir, CYCLE)
    run_obs2ioda(config_dir, CYCLE)

    with pytest.raises(Obs2IODAValidationError, match="invalid IODA header"):
        validate_obs2ioda(config_dir, CYCLE)


def _add_runtime_config(config_dir: Path, tmp_path: Path, ldd_output: str) -> None:
    linker = tmp_path / "fake-ldd"
    linker.write_text(f"#!/bin/sh\nprintf '%s\\n' {ldd_output!r}\n", encoding="utf-8")
    linker.chmod(0o755)
    content = yaml.safe_load((config_dir / "obs2ioda.yaml").read_text(encoding="utf-8"))
    content["obs2ioda"]["runtime"] = {
        "library_paths": ["{work_dir}/site-libs", str(tmp_path / "shared-libs")],
        "dependency_checks": [sys.executable],
        "linker_command": str(linker),
    }
    (config_dir / "obs2ioda.yaml").write_text(yaml.safe_dump(content), encoding="utf-8")


def test_obs2ioda_runtime_dependencies_resolve_and_remain_child_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = write_config(tmp_path)
    library = tmp_path / "shared-libs" / "libexample.so"
    library.parent.mkdir()
    library.write_bytes(b"library")
    _add_runtime_config(config_dir, tmp_path, f"libexample.so => {library} (0x1)")
    content = yaml.safe_load((config_dir / "obs2ioda.yaml").read_text(encoding="utf-8"))
    content["obs2ioda"]["converters"][0]["argv"][2] = (
        "import os; from pathlib import Path; "
        "Path(r'{work_dir}/sample.nc4').write_text(os.environ['LD_LIBRARY_PATH'])"
    )
    (config_dir / "obs2ioda.yaml").write_text(yaml.safe_dump(content), encoding="utf-8")
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)

    report = json.loads(doctor_obs2ioda(config_dir, CYCLE).read_text())
    linker_check = report["runtime"]["linker_checks"][0]
    assert linker_check["valid"] is True
    assert linker_check["missing_libraries"] == []
    assert linker_check["resolved_libraries"][0]["path"] == str(library)
    assert "LD_LIBRARY_PATH" not in os.environ

    run = prepare_obs2ioda(config_dir, CYCLE)
    manifest = json.loads(run.manifest_path.read_text())
    assert manifest["runtime"]["library_paths"] == [
        str(run.work_dir / "site-libs"),
        str(tmp_path / "shared-libs"),
    ]
    run_obs2ioda(config_dir, CYCLE)
    assert (run.work_dir / "sample.nc4").read_text().split(os.pathsep)[:2] == manifest["runtime"]["library_paths"]
    assert "LD_LIBRARY_PATH" not in os.environ


def test_obs2ioda_doctor_and_run_fail_early_for_missing_dependency(tmp_path: Path) -> None:
    config_dir = write_config(tmp_path)
    _add_runtime_config(config_dir, tmp_path, "libmissing.so => not found")

    with pytest.raises(Obs2IODADoctorError, match="libmissing.so"):
        doctor_obs2ioda(config_dir, CYCLE)
    report = json.loads(
        (config_dir / "work/obs2ioda/20180415T000000Z/.monan-jedi-workflow/obs2ioda-doctor.json").read_text()
    )
    assert report["valid"] is False
    assert report["runtime"]["linker_checks"][0]["missing_libraries"] == ["libmissing.so"]

    run = prepare_obs2ioda(config_dir, CYCLE)
    with pytest.raises(Obs2IODADoctorError, match="libmissing.so"):
        run_obs2ioda(config_dir, CYCLE)
    manifest = json.loads(run.manifest_path.read_text())
    assert manifest["state"] == "failed-runtime-dependencies"
    assert manifest["runs"] == []
