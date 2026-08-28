from pathlib import Path

import yaml

from monan_jedi_workflow.cycle_doctor import doctor_cycle


def _write_minimal_jedi_config(root: Path) -> None:
    (root / "jedi.yaml").write_text(
        yaml.safe_dump(
            {
                "jedi": {
                    "cycle": {"first_cycle": "2018-04-15T00:00:00Z"},
                    "run_dir": "work/{cycle_id}",
                    "background": {
                        "initial_source": "initial.nc",
                        "source": "previous.nc",
                        "target": "background.nc",
                    },
                    "pbs": {"command": ["true"]},
                }
            }
        ),
        encoding="utf-8",
    )


def test_cycle_doctor_reports_missing_stage_files(tmp_path: Path) -> None:
    _write_minimal_jedi_config(tmp_path)

    report = doctor_cycle(tmp_path, "2018-04-15T00:00:00Z")

    assert report["ready"] is False
    checks = {item["name"]: item for item in report["checks"]}
    assert checks["mpas.yaml"]["ok"] is False
    assert checks["obs2ioda.yaml"]["ok"] is False


def test_cycle_doctor_can_check_analysis_only(tmp_path: Path) -> None:
    _write_minimal_jedi_config(tmp_path)

    report = doctor_cycle(
        tmp_path,
        "2018-04-15T00:00:00Z",
        require_observations=False,
        require_forecast=False,
    )

    assert report["ready"] is True
