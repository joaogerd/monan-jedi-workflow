from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.nmc_campaign import (
    bflow_manifest_path,
    build_nmc_campaign,
    write_bflow_manifest,
    write_nmc_campaign_plan,
)


def test_campaign_plans_four_pairs_and_exports_bflow_manifest(tmp_path: Path) -> None:
    case = tmp_path / "case"
    case.mkdir()
    (case / "inputs.yaml").write_text(
        """inputs:
  sources:
    gfs:
      provider: local
      target: inputs/gfs_{cycle_yyyymmddhh}.grib2
      format: grib2
      mesh: x1.10242
""",
        encoding="utf-8",
    )
    (case / "workflow.yaml").write_text(
        """workflow:
  mode: bmatrix
  mesh: x1.10242
  input_source: gfs
  use_wps: auto
  bmatrix:
    campaign:
      start_valid_time: "2026-06-22T00:00:00Z"
      end_valid_time: "2026-06-22T18:00:00Z"
      valid_interval_hours: 6
      minimum_pairs: 4
      output_dir: campaign
      forecasts:
        f024_hours: 24
        f048_hours: 48
        products:
          restart: restart.{mpas_valid_file_time}.nc
          bflow: mpasout.{mpas_valid_file_time}.nc
""",
        encoding="utf-8",
    )
    (case / "mpas.yaml").write_text(
        """mpas:
  lead_hours: 24
  run_dir: work/forecast/{cycle_id}_f{lead_hours}
""",
        encoding="utf-8",
    )
    (case / "mpas_init.yaml").write_text("mpas_init: {}\n", encoding="utf-8")
    (case / "wps.yaml").write_text("wps: {}\n", encoding="utf-8")

    campaign = build_nmc_campaign(case)

    assert len(campaign.pairs) == 4
    assert len(campaign.initializations) == 8
    assert campaign.use_wps is True
    assert write_nmc_campaign_plan(campaign).is_file()
    assert campaign.pairs[0].f048.init_time == "2026-06-20T00:00:00Z"
    assert campaign.pairs[0].f024.init_time == "2026-06-21T00:00:00Z"

    for pair in campaign.pairs:
        for product in (pair.f048, pair.f024):
            product.restart.parent.mkdir(parents=True, exist_ok=True)
            product.restart.write_bytes(b"restart")
            product.bflow.write_bytes(b"da_state")

    manifest, report = write_bflow_manifest(campaign, with_checksum=True)
    lines = manifest.read_text(encoding="utf-8").splitlines()

    assert manifest == bflow_manifest_path(campaign)
    assert lines[0] == "valid_time\tf048\tf024"
    assert len(lines) == 5
    assert report.is_file()
