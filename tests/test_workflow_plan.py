from __future__ import annotations

import json
from pathlib import Path

from monan_jedi_workflow.workflow_plan import (
    build_workflow_plan,
    export_bmatrix_contract,
    write_workflow_plan,
)


def _write(path: Path, content: str = "x: {}\n") -> None:
    path.write_text(content, encoding="utf-8")


def test_cycle_plan_selects_wps_for_grib_and_assimilation(tmp_path: Path) -> None:
    config = tmp_path / "case"
    config.mkdir()
    (config / "input.grib2").write_bytes(b"grib")
    _write(
        config / "inputs.yaml",
        """inputs:
  sources:
    gfs:
      provider: local
      target: input.grib2
      format: grib2
      mesh: x1.10242
""",
    )
    _write(
        config / "workflow.yaml",
        """workflow:
  mode: cycle
  input_source: gfs
  mesh: x1.10242
  use_wps: auto
""",
    )
    for filename in ("wps.yaml", "mpas_init.yaml", "mpas.yaml", "experiment.yaml", "variables.yaml", "observations.yaml", "runtime.yaml", "pbs.yaml"):
        _write(config / filename)

    plan = build_workflow_plan(config, "2018-04-15T00:00:00Z")
    names = [step.name for step in plan.steps]

    assert plan.use_wps is True
    assert names[:4] == ["inputs-validate", "wps-prepare", "wps-run", "wps-validate"]
    assert "jedi-submit" in names
    assert write_workflow_plan(plan).is_file()


def test_bmatrix_plan_exports_only_a_portable_handoff(tmp_path: Path) -> None:
    config = tmp_path / "case"
    config.mkdir()
    (config / "input.nc").write_bytes(b"input")
    (config / "samples").mkdir()
    (config / "samples/one.nc").write_bytes(b"one")
    (config / "samples/two.nc").write_bytes(b"two")
    _write(
        config / "inputs.yaml",
        """inputs:
  sources:
    system:
      provider: infrastructure
      target: input.nc
      format: netcdf
""",
    )
    _write(
        config / "workflow.yaml",
        """workflow:
  mode: bmatrix
  input_source: system
  use_wps: never
  bmatrix:
    sample_glob: samples/*.nc
    minimum_samples: 2
    output_dir: handoff
""",
    )
    _write(config / "mpas_init.yaml")
    _write(config / "mpas.yaml")

    plan = build_workflow_plan(config, "2018-04-15T00:00:00Z")
    handoff = export_bmatrix_contract(plan, with_checksum=True)
    payload = json.loads(handoff.read_text(encoding="utf-8"))

    assert [step.name for step in plan.steps][-1] == "bmatrix-export-contract"
    assert len(payload["samples"]) == 2
    assert payload["consumer_contract"]["pipeline"] == "refactor/bflow-python-pipeline"
