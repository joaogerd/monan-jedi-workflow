from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.corrected_campaign import (
    _cycles,
    build_corrected_campaign_workflow,
    materialize_corrected_campaign,
)
from monan_jedi_workflow.stage_config import StageConfigurationError


def _task_map(document: dict) -> dict[str, dict]:
    return {task["name"]: task for task in document["tasks"]}


def _initialization_task_map(document: dict) -> dict[str, dict]:
    return {task["name"]: task for task in document["initialization"]["tasks"]}


@pytest.mark.parametrize(
    ("end_cycle", "expected_cycles"),
    [
        ("2018-04-18T00:00:00Z", 13),
        ("2018-04-22T00:00:00Z", 29),
        ("2018-05-15T00:00:00Z", 121),
        ("2019-04-15T00:00:00Z", 1461),
    ],
)
def test_campaign_cycle_count_is_inclusive(end_cycle: str, expected_cycles: int) -> None:
    cycles = _cycles("2018-04-15T00:00:00Z", end_cycle)
    assert len(cycles) == expected_cycles
    assert cycles[0].strftime("%Y-%m-%dT%H:%M:%SZ") == "2018-04-15T00:00:00Z"
    assert cycles[-1].strftime("%Y-%m-%dT%H:%M:%SZ") == end_cycle


def test_72_hour_campaign_uses_one_native_cycle_graph() -> None:
    document = build_corrected_campaign_workflow(
        start_cycle="2018-04-15T00:00:00Z",
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
    )
    tasks = _task_map(document)
    initialization = _initialization_task_map(document)

    assert document["workflow"]["name"] == "monan_jedi_corrected_campaign"
    assert document["cycle"] == {
        "start": "2018-04-15T00:00:00Z",
        "end": "2018-04-18T00:00:00Z",
        "step": "PT6H",
    }
    assert set(initialization) == {
        "mpas_initial_prepare",
        "mpas_initial_submit",
        "mpas_initial_wait",
        "mpas_initial_validate",
        "mpas_initial_gate",
        "initial_background",
    }
    assert set(tasks) == {
        "background_check",
        "observations_doctor",
        "observations_prepare",
        "observations_run",
        "observations_validate",
        "observations_gate",
        "jedi_prepare",
        "jedi_submit",
        "jedi_wait",
        "jedi_validate",
        "jedi_gate",
        "mpas_prepare",
        "mpas_submit",
        "mpas_wait",
        "mpas_validate",
        "mpas_gate",
        "next_background",
    }

    timestamp = re.compile(r"20\d{8}")
    assert not any(timestamp.search(name) for name in initialization | tasks)

    assert tasks["jedi_prepare"]["depends_on"] == [
        "background_check",
        "observations_gate",
    ]
    assert tasks["mpas_prepare"]["depends_on"] == ["jedi_gate"]
    assert tasks["mpas_prepare"]["cycle_scope"] == "not_last"
    assert tasks["next_background"]["cycle_scope"] == "not_last"
    assert tasks["next_background"]["depends_on"] == ["mpas_gate"]


def test_last_cycle_mpas_scope_is_scientific_configuration_not_hardcoded() -> None:
    cycling_only = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
        run_mpas_on_last_cycle=False,
    )
    with_forecast = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
        run_mpas_on_last_cycle=True,
    )

    assert _task_map(cycling_only)["mpas_prepare"]["cycle_scope"] == "not_last"
    assert _task_map(with_forecast)["mpas_prepare"]["cycle_scope"] == "all"
    assert _task_map(with_forecast)["mpas_validate"]["cycle_scope"] == "all"
    assert _task_map(with_forecast)["next_background"]["cycle_scope"] == "not_last"


def test_structural_task_count_is_constant_from_three_days_to_one_year() -> None:
    documents = {
        label: build_corrected_campaign_workflow(
            start_cycle="2018-04-15T00:00:00Z",
            end_cycle=end,
            experiment_dir="/tmp/campaign",
        )
        for label, end in {
            "3d": "2018-04-18T00:00:00Z",
            "7d": "2018-04-22T00:00:00Z",
            "30d": "2018-05-15T00:00:00Z",
            "365d": "2019-04-15T00:00:00Z",
        }.items()
    }

    structural_counts = {
        label: len(document["initialization"]["tasks"]) + len(document["tasks"])
        for label, document in documents.items()
    }
    assert len(set(structural_counts.values())) == 1

    task_ids = {
        label: (
            tuple(task["name"] for task in document["initialization"]["tasks"]),
            tuple(task["name"] for task in document["tasks"]),
        )
        for label, document in documents.items()
    }
    assert len(set(task_ids.values())) == 1

    rendered_sizes = {
        label: len(yaml.safe_dump(document, sort_keys=False).encode("utf-8"))
        for label, document in documents.items()
    }
    assert max(rendered_sizes.values()) - min(rendered_sizes.values()) < 256


def test_campaign_validation_gates_are_content_fingerprinted() -> None:
    document = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
    )
    gates = [
        task
        for task in [*document["initialization"]["tasks"], *document["tasks"]]
        if task["name"].endswith("_gate")
    ]

    assert {task["name"] for task in gates} == {
        "mpas_initial_gate",
        "observations_gate",
        "jedi_gate",
        "mpas_gate",
    }
    for task in gates:
        assert task["argv"][1] == "validation-gate"
        assert task["input_fingerprint"] == "sha256"
        assert len(task["inputs"]["required"]) == 1
        assert task["inputs"]["required"][0].endswith("validation.json")


def test_background_interface_is_uniform_for_first_and_later_cycles() -> None:
    document = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
    )
    tasks = _task_map(document)
    background = tasks["background_check"]
    jedi = tasks["jedi_prepare"]

    assert "{cycle_time}" in " ".join(background["argv"])
    assert any("{cycle_id}" in path for path in background["inputs"]["required"])
    assert "{experiment_dir}/work/background/{cycle_id}/trajectory.nc" in jedi["inputs"]["required"]
    assert "{experiment_dir}/work/background/{cycle_id}/state.nc" in jedi["inputs"]["required"]


def test_observations_belong_to_current_cycle() -> None:
    document = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
    )
    tasks = _task_map(document)

    assert tasks["observations_doctor"]["cycle_scope"] == "all"
    assert tasks["observations_prepare"]["cycle_scope"] == "all"
    assert "{cycle_time}" in tasks["observations_doctor"]["argv"]
    assert "{cycle_yyyymmddhh}" in tasks["jedi_prepare"]["inputs"]["required"][3]


def test_campaign_rejects_non_validated_start_cycle() -> None:
    with pytest.raises(StageConfigurationError, match="validated first cycle"):
        build_corrected_campaign_workflow(
            start_cycle="2018-04-15T06:00:00Z",
            end_cycle="2018-04-18T00:00:00Z",
            experiment_dir="/tmp/campaign",
        )


def test_materialized_campaign_records_compact_scope(tmp_path: Path) -> None:
    document = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir=str(tmp_path / "campaign"),
    )
    rendered = tmp_path / "workflow.yaml"
    rendered.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    loaded = yaml.safe_load(rendered.read_text(encoding="utf-8"))

    assert loaded["context"]["experiment_dir"] == str(tmp_path / "campaign")
    assert loaded["cycle"]["start"] == "2018-04-15T00:00:00Z"
    assert loaded["cycle"]["end"] == "2018-04-18T00:00:00Z"
    assert len(loaded["initialization"]["tasks"]) == 6
    assert len(loaded["tasks"]) == 17
    assert materialize_corrected_campaign is not None
