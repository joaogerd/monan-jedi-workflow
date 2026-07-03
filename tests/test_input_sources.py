from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from monan_jedi_workflow.input_sources import (
    InputValidationError,
    resolve_input_source,
    validate_input_source,
)


def test_local_source_validates_checksum_coverage_and_mesh(tmp_path: Path) -> None:
    config = tmp_path / "case"
    config.mkdir()
    data = config / "gfs_2018041500.grib2"
    data.write_bytes(b"gfs")
    checksum = hashlib.sha256(b"gfs").hexdigest()
    (config / "inputs.yaml").write_text(
        f"""inputs:
  sources:
    gfs:
      provider: local
      target: gfs_{{cycle_yyyymmddhh}}.grib2
      format: grib2
      mesh: x1.10242
      min_bytes: 3
      suffixes: [.grib2]
      sha256: {checksum}
      coverage:
        start: "2018-04-14T00:00:00Z"
        end: "2018-04-16T00:00:00Z"
""",
        encoding="utf-8",
    )

    source = resolve_input_source(config, "gfs", "2018-04-15T00:00:00Z")
    report = validate_input_source(source, required_mesh="x1.10242", with_checksum=True)

    assert report["requires_wps"] is True
    assert report["product"]["sha256"] == checksum


def test_source_rejects_mesh_mismatch_before_expensive_stages(tmp_path: Path) -> None:
    config = tmp_path / "case"
    config.mkdir()
    (config / "input.nc").write_bytes(b"state")
    (config / "inputs.yaml").write_text(
        """inputs:
  sources:
    local:
      provider: infrastructure
      target: input.nc
      format: netcdf
      mesh: x1.40962
""",
        encoding="utf-8",
    )

    source = resolve_input_source(config, "local", "2018-04-15T00:00:00Z")
    with pytest.raises(InputValidationError, match="declares mesh"):
        validate_input_source(source, required_mesh="x1.10242")
