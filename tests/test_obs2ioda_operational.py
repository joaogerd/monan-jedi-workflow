from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.obs2ioda_stage import (
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
