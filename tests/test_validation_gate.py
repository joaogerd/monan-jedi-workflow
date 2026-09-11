import json
from pathlib import Path

import pytest

from monan_jedi_workflow.validation_gate import (
    ValidationGateError,
    require_valid_manifest,
)


def test_require_valid_manifest_accepts_valid_true(tmp_path: Path) -> None:
    manifest = tmp_path / "validation.json"
    manifest.write_text(json.dumps({"valid": True, "job_id": "123.pbs"}), encoding="utf-8")

    payload = require_valid_manifest(manifest)

    assert payload["valid"] is True
    assert payload["job_id"] == "123.pbs"


def test_require_valid_manifest_rejects_false(tmp_path: Path) -> None:
    manifest = tmp_path / "validation.json"
    manifest.write_text(json.dumps({"valid": False}), encoding="utf-8")

    with pytest.raises(ValidationGateError, match="not valid=true"):
        require_valid_manifest(manifest)


def test_require_valid_manifest_rejects_missing(tmp_path: Path) -> None:
    with pytest.raises(ValidationGateError, match="does not exist"):
        require_valid_manifest(tmp_path / "missing.json")


def test_require_valid_manifest_rejects_invalid_json(tmp_path: Path) -> None:
    manifest = tmp_path / "validation.json"
    manifest.write_text("not-json", encoding="utf-8")

    with pytest.raises(ValidationGateError, match="cannot read validation manifest"):
        require_valid_manifest(manifest)
