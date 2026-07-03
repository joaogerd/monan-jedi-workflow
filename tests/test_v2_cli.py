"""Smoke tests for V2 command-line entry points."""

from pathlib import Path

from monan_jedi_workflow.cli_v2 import main


def test_nmc_pairs_dry_run_writes_resolved_configuration(tmp_path: Path) -> None:
    """The public V2 command must accept the documented dry-run invocation."""
    config = tmp_path / "case.yaml"
    config.write_text(
        """case:
  name: cli-smoke
model:
  mpas:
    forecast_products:
      root: /tmp/mpas-products
      restart_template: '{init_yyyymmddhh}/restart.{mpas_valid_file_time}.nc'
      state_template: '{init_yyyymmddhh}/mpasout.{mpas_valid_file_time}.nc'
bmatrix:
  nmc_pairs:
    start_valid_time: '2026-06-22T00:00:00Z'
    end_valid_time: '2026-06-25T00:00:00Z'
""",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    assert main(["nmc-pairs", "--config", str(config), "--workspace", str(workspace), "--dry-run"]) == 0
    assert (workspace / ".monan-jedi-workflow/resolved-config.yaml").is_file()
