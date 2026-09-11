from __future__ import annotations

from pathlib import Path

import pytest

import monan_jedi_workflow.corrected_replay as replay


def test_absolutize_case_path_preserves_placeholders_and_anchors_source_case(
    tmp_path: Path,
) -> None:
    source_case = tmp_path / "source-case"
    value = "templates/{cycle_id}/namelist.atmosphere"

    resolved = replay._absolutize_case_path(value, source_case)

    assert resolved == str(
        (source_case / "templates/{cycle_id}/namelist.atmosphere").resolve(
            strict=False
        )
    )
    assert "{cycle_id}" in resolved


def test_materializer_removes_partial_destination_when_case_copy_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "replay"

    monkeypatch.setattr(
        replay,
        "_initial_inputs",
        lambda _path: {},
    )

    def fail_after_partial_copy(_source: Path, target: Path) -> None:
        target.mkdir(parents=True)
        (target / "partial.txt").write_text("partial", encoding="utf-8")
        raise OSError("simulated copy failure")

    monkeypatch.setattr(replay, "_copy_clean_case", fail_after_partial_copy)

    with pytest.raises(OSError, match="simulated copy failure"):
        replay.materialize_corrected_replay(
            initial_jedi_case=tmp_path / "initial",
            cycling_jedi_case=tmp_path / "cycling",
            mpas_case=tmp_path / "mpas",
            obs2ioda_config=tmp_path / "obs.yaml",
            workflow_template=tmp_path / "workflow.yaml",
            destination=destination,
        )

    assert not destination.exists()
