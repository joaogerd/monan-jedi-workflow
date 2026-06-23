from __future__ import annotations

import yaml

from monan_jedi_workflow.manifest import (
    create_stage_manifest,
    file_fingerprint,
    stable_config_hash,
    write_manifest,
)


def test_config_hash_is_stable_for_equivalent_mappings() -> None:
    first = {"b": 2, "a": {"x": 1}}
    second = {"a": {"x": 1}, "b": 2}

    assert stable_config_hash(first) == stable_config_hash(second)


def test_stage_manifest_records_and_updates_status() -> None:
    manifest = create_stage_manifest(
        experiment="cycle_1day",
        cycle_id="2018041500",
        stage="assimilate",
        attempt=1,
        resolved_config={"run": {"tasks": 64}},
        argv=["python", "-m", "monan_jedi_workflow"],
        executor="local",
        inputs=({"path": "background.nc"},),
    )

    assert manifest.status == "planned"
    assert manifest.argv == ("python", "-m", "monan_jedi_workflow")
    assert manifest.inputs == ({"path": "background.nc"},)

    updated = manifest.with_status("success", outputs=({"path": "analysis.nc"},))

    assert updated.status == "success"
    assert updated.outputs == ({"path": "analysis.nc"},)
    assert updated.created_at == manifest.created_at
    assert updated.updated_at >= manifest.updated_at


def test_write_manifest_creates_yaml_file(tmp_path) -> None:
    manifest = create_stage_manifest(
        experiment="cycle_1day",
        cycle_id="2018041500",
        stage="prepare",
        attempt=1,
        resolved_config={"cycle": "2018041500"},
    )
    path = tmp_path / "prepare" / "manifest.yaml"

    write_manifest(path, manifest)

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["experiment"] == "cycle_1day"
    assert data["stage"] == "prepare"
    assert data["status"] == "planned"
    assert not path.with_suffix(".yaml.tmp").exists()


def test_file_fingerprint_includes_size_and_hash(tmp_path) -> None:
    path = tmp_path / "input.txt"
    path.write_text("content", encoding="utf-8")

    fingerprint = file_fingerprint(path)

    assert fingerprint["path"] == str(path)
    assert fingerprint["size_bytes"] == 7
    assert len(fingerprint["sha256"]) == 64
