"""MPAS example configuration test."""

from pathlib import Path

from monan_jedi_workflow.components.model.mpas.forecast_config import compile_mpas_forecast
from monan_jedi_workflow.core.config import load_mapping
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def test_documented_mpas_example_compiles(tmp_path: Path) -> None:
    """The public MPAS example remains accepted by the compiler."""
    config = load_mapping(Path("examples/v2/model/mpas_forecast.yaml.example"))
    stage = compile_mpas_forecast(config, workspace=tmp_path, init_time="2026-06-20T00:00:00Z", lead_hours=48, backend=LocalProcessBackend())
    assert stage.product.valid_time == "2026-06-22_00:00:00"
