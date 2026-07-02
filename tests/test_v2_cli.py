"""Smoke tests for V2 command-line entry points."""

from pathlib import Path

from monan_jedi_workflow.cli_v2 import main
from monan_jedi_workflow.cli_validate_nmc import main as validate_nmc


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


def test_nmc_campaign_dry_run_builds_full_dag(tmp_path: Path) -> None:
    """The full NMC campaign command plans init, forecasts, and hand-off."""
    config = Path("examples/v2/bmatrix/nmc_campaign.yaml.example")
    workspace = tmp_path / "campaign"
    assert main(["nmc-campaign", "--config", str(config), "--workspace", str(workspace), "--dry-run"]) == 0
    assert (workspace / ".monan-jedi-workflow/resolved-config.yaml").is_file()
    assert (workspace / ".monan-jedi-workflow/provenance.json").is_file()


def test_nmc_campaign_jaci_dry_run_uses_site_profile_without_qsub(tmp_path: Path) -> None:
    """JACI planning must compile resource profiles without submitting jobs."""
    campaign = Path("examples/v2/bmatrix/nmc_campaign.yaml.example")
    site = Path("examples/v2/platforms/jaci.yaml.example")
    workspace = tmp_path / "jaci-campaign"
    assert main([
        "nmc-campaign",
        "--config", str(campaign),
        "--config", str(site),
        "--workspace", str(workspace),
        "--backend", "jaci-pbs",
        "--dry-run",
    ]) == 0
    assert (workspace / ".monan-jedi-workflow/resolved-config.yaml").is_file()


def test_stage_run_dry_run_plans_one_declared_campaign_stage(tmp_path: Path) -> None:
    """External orchestration tasks can plan one named V2 stage."""
    campaign = Path("examples/v2/bmatrix/nmc_campaign.yaml.example")
    workspace = tmp_path / "stage"
    assert main([
        "stage",
        "run",
        "--stage", "mpas_init_2026062000",
        "--config", str(campaign),
        "--workspace", str(workspace),
        "--dry-run",
    ]) == 0
    assert (workspace / ".monan-jedi-workflow/provenance.json").is_file()


def test_nmc_audit_cli_writes_invalid_report_for_empty_workspace(tmp_path: Path) -> None:
    """The audit CLI returns a nonzero status and persistent report on failure."""
    campaign = Path("examples/v2/bmatrix/nmc_campaign.yaml.example")
    workspace = tmp_path / "audit"
    assert validate_nmc(["--config", str(campaign), "--workspace", str(workspace)]) == 2
    assert (workspace / ".monan-jedi-workflow/validation/nmc-campaign.json").is_file()
