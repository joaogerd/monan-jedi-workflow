from __future__ import annotations

import json
from pathlib import Path

import yaml

from monan_jedi_workflow.background_stage import check_background, publish_background


def _mpas_config(root: Path, experiment: Path) -> None:
    root.mkdir(parents=True)
    (root / "mpas.yaml").write_text(
        yaml.safe_dump(
            {
                "mpas": {
                    "lead_hours": 6,
                    "run_dir": str(experiment / "work/source-mpas/{cycle_id}"),
                    "links": [],
                    "templates": [],
                    "pbs": {
                        "queue": "pesqmini",
                        "ncpus": 1,
                        "mpiprocs": 1,
                        "walltime": "00:10:00",
                        "command": ["true"],
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_publish_background_normalizes_mpas_plus3_and_plus6_products(tmp_path: Path) -> None:
    experiment = tmp_path / "experiment"
    config = experiment / "initialization"
    _mpas_config(config, experiment)

    source = experiment / "work/source-mpas/20180414T180000Z"
    source.mkdir(parents=True)
    trajectory = source / "mpasout.2018-04-14_21.00.00.nc"
    state = source / "mpasout.2018-04-15_00.00.00.nc"
    trajectory.write_bytes(b"trajectory")
    state.write_bytes(b"state")

    publication = publish_background(
        experiment,
        mpas_config_dir=config,
        source_cycle_time="2018-04-14T18:00:00Z",
        target_cycle_time="2018-04-15T00:00:00Z",
    )

    target = experiment / "work/background/20180415T000000Z"
    assert publication.directory == target
    assert (target / "trajectory.nc").is_symlink()
    assert (target / "trajectory.nc").resolve() == trajectory.resolve()
    assert (target / "state.nc").is_symlink()
    assert (target / "state.nc").resolve() == state.resolve()
    manifest = json.loads((target / "background.json").read_text())
    assert manifest["source_cycle"] == "2018-04-14T18:00:00Z"
    assert manifest["target_cycle"] == "2018-04-15T00:00:00Z"
    assert manifest["trajectory_source"] == str(trajectory)
    assert manifest["state_source"] == str(state)

    # Publication is restart-safe when the same products are already linked.
    again = publish_background(
        experiment,
        mpas_config_dir=config,
        source_cycle_time="2018-04-14T18:00:00Z",
        target_cycle_time="2018-04-15T00:00:00Z",
    )
    assert again == publication


def test_check_background_publishes_small_validation_manifest(tmp_path: Path) -> None:
    experiment = tmp_path / "experiment"
    background = experiment / "work/background/20180415T000000Z"
    background.mkdir(parents=True)
    (background / "trajectory.nc").write_bytes(b"trajectory")
    (background / "state.nc").write_bytes(b"state")

    validation = check_background(experiment, "2018-04-15T00:00:00Z")

    assert validation.is_file()
    payload = json.loads(validation.read_text())
    assert payload["cycle_time"] == "2018-04-15T00:00:00Z"
    assert payload["cycle_id"] == "20180415T000000Z"
    assert payload["ready"] is True
    assert payload["trajectory"].endswith("trajectory.nc")
    assert payload["state"].endswith("state.nc")
