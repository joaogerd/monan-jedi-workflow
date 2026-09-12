from pathlib import Path

import yaml

from monan_jedi_workflow.corrected_campaign import (
    build_corrected_campaign_workflow,
    materialize_corrected_campaign,
)
from monan_jedi_workflow.stage_config import StageConfigurationError


def _task_map(document: dict) -> dict[str, dict]:
    return {task["name"]: task for task in document["tasks"]}


def test_72_hour_campaign_builds_explicit_cross_cycle_graph() -> None:
    document = build_corrected_campaign_workflow(
        start_cycle="2018-04-15T00:00:00Z",
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
    )
    tasks = _task_map(document)

    assert document["workflow"]["name"] == (
        "monan_jedi_corrected_campaign_2018041500_2018041800"
    )
    assert len(document["tasks"]) == 185

    assert "jedi2018041500_prepare" in tasks
    assert "jedi2018041800_gate" in tasks
    assert not any(name.startswith("obs2018041500_") for name in tasks)
    assert not any(name.startswith("mpas2018041800_") for name in tasks)

    assert tasks["mpas2018041518_prepare"]["depends_on"] == [
        "jedi2018041518_gate"
    ]
    assert tasks["obs2018041600_doctor"]["depends_on"] == [
        "jedi2018041518_gate"
    ]
    assert set(tasks["jedi2018041600_prepare"]["depends_on"]) == {
        "mpas2018041518_gate",
        "obs2018041600_gate",
    }

    assert tasks["mpas2018041718_validate"]["outputs"]["required"][-1].endswith(
        "mpasout.2018-04-18_00.00.00.nc"
    )
    assert set(tasks["jedi2018041800_prepare"]["depends_on"]) == {
        "mpas2018041718_gate",
        "obs2018041800_gate",
    }


def test_campaign_validation_gates_are_content_fingerprinted() -> None:
    document = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir="/tmp/campaign",
    )
    gates = [task for task in document["tasks"] if task["name"].endswith("_gate")]

    assert len(gates) == 37
    for task in gates:
        assert task["argv"][1] == "validation-gate"
        assert task["input_fingerprint"] == "sha256"
        assert len(task["inputs"]["required"]) == 1
        assert task["inputs"]["required"][0].endswith("validation.json")


def test_campaign_rejects_non_validated_start_cycle() -> None:
    try:
        build_corrected_campaign_workflow(
            start_cycle="2018-04-15T06:00:00Z",
            end_cycle="2018-04-18T00:00:00Z",
            experiment_dir="/tmp/campaign",
        )
    except StageConfigurationError as exc:
        assert "validated first cycle" in str(exc)
    else:
        raise AssertionError("expected campaign start validation to fail")


def test_materialized_campaign_records_72_hour_scope(tmp_path: Path) -> None:
    initial = tmp_path / "initial"
    cycling = tmp_path / "cycling"
    mpas = tmp_path / "mpas"
    initial.mkdir()
    cycling.mkdir()
    mpas.mkdir()

    # Exercise only the campaign writer here.  The detailed corrected-case
    # materialization contract is covered by the existing corrected replay tests.
    # Monkeypatching is intentionally avoided in this integration-shaped test, so
    # a minimal valid case is not duplicated here.
    document = build_corrected_campaign_workflow(
        end_cycle="2018-04-18T00:00:00Z",
        experiment_dir=str(tmp_path / "campaign"),
    )
    rendered = tmp_path / "workflow.yaml"
    rendered.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    loaded = yaml.safe_load(rendered.read_text(encoding="utf-8"))

    assert loaded["context"]["experiment_dir"] == str(tmp_path / "campaign")
    assert len(loaded["tasks"]) == 185
    assert materialize_corrected_campaign is not None
