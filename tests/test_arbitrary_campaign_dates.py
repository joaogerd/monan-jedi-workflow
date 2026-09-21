from __future__ import annotations

from pathlib import Path

import yaml

from monan_jedi_workflow.corrected_campaign import (
    _cycles,
    _initialization_tasks,
    _parse_cycle,
    _patch_jedi_native,
    build_corrected_campaign_workflow,
)


def test_august_2025_seven_day_campaign_has_29_inclusive_cycles() -> None:
    cycles = _cycles(
        "2025-08-01T00:00:00Z",
        "2025-08-08T00:00:00Z",
    )

    assert len(cycles) == 29
    assert cycles[0].isoformat() == "2025-08-01T00:00:00+00:00"
    assert cycles[-1].isoformat() == "2025-08-08T00:00:00+00:00"


def test_initialization_for_august_2025_starts_six_hours_before_first_analysis() -> None:
    tasks = _initialization_tasks(_parse_cycle("2025-08-01T00:00:00Z"))
    by_name = {task["name"]: task for task in tasks}

    prepare = by_name["mpas_initial_prepare"]
    publish = by_name["initial_background"]

    assert "2025-07-31T18:00:00Z" in prepare["argv"]
    assert "2025-07-31T18:00:00Z" in publish["argv"]
    assert "2025-08-01T00:00:00Z" in publish["argv"]


def test_august_2025_workflow_remains_structurally_compact() -> None:
    document = build_corrected_campaign_workflow(
        start_cycle="2025-08-01T00:00:00Z",
        end_cycle="2025-08-08T00:00:00Z",
        experiment_dir="/tmp/campaign",
    )

    assert document["cycle"]["start"] == "2025-08-01T00:00:00Z"
    assert document["cycle"]["end"] == "2025-08-08T00:00:00Z"
    assert len(document["initialization"]["tasks"]) == 6
    assert len(document["tasks"]) == 17


def test_jedi_first_cycle_is_derived_from_campaign_start(tmp_path: Path) -> None:
    destination = tmp_path / "campaign"
    destination.mkdir()

    (destination / "jedi.yaml").write_text(
        yaml.safe_dump(
            {
                "jedi": {
                    "cycle": {},
                    "background": {
                        "initial_source": "/old/trajectory.nc",
                        "source": "/old/trajectory.nc",
                    },
                    "analysis_base_state": {
                        "source": "/old/state.nc",
                        "expected_variable_count": 62,
                    },
                    "links": [
                        {"source": "/old/sondes.h5", "target": "sondes_obs_test.h5"},
                        {"source": "/old/sfc.h5", "target": "sfc_obs_test.h5"},
                        {"source": "/old/gnssro.h5", "target": "gnssro_obs_test.h5"},
                    ],
                    "pbs": {"mpiprocs": 128},
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    _patch_jedi_native(destination, "2025-08-01T00:00:00Z")

    document = yaml.safe_load(
        (destination / "jedi.yaml").read_text(encoding="utf-8")
    )
    assert document["jedi"]["cycle"]["first_cycle"] == "2025-08-01T00:00:00Z"


def test_historical_2018_default_remains_backward_compatible() -> None:
    document = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
    )

    assert document["cycle"]["start"] == "2018-04-15T00:00:00Z"
