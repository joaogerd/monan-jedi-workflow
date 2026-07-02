"""MPAS forecast configuration compiler tests."""

from pathlib import Path

from monan_jedi_workflow.components.model.mpas.forecast_config import compile_mpas_forecast
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def test_compiler_resolves_product_and_run_paths(tmp_path: Path) -> None:
    """A minimal MPAS mapping compiles to an explicit forecast stage."""
    config = {"model": {"mpas": {
        "forecast_products": {"root": str(tmp_path), "restart_template": "restart.{mpas_valid_file_time}.nc", "state_template": "state.{mpas_valid_file_time}.nc"},
        "forecast": {"run_dir": "runs/{init_yyyymmddhh}", "argv": ["/bin/true"]},
    }}}
    stage = compile_mpas_forecast(config, workspace=tmp_path, init_time="2026-06-20T00:00:00Z", lead_hours=48, backend=LocalProcessBackend())
    assert stage.run_dir == tmp_path / "runs/2026062000"
    assert stage.product.valid_time == "2026-06-22_00:00:00"
