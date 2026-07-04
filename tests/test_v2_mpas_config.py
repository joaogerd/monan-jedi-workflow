"""MPAS forecast configuration compiler tests."""

from pathlib import Path

import pytest

from monan_jedi_workflow.components.model.mpas.forecast_config import (
    MpasForecastConfigurationError,
    compile_mpas_forecast,
)
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def _config(root: Path, resources: dict[str, object] | None = None) -> dict[str, object]:
    """Build one minimal forecast configuration with optional resources."""
    return {"model": {"mpas": {
        "forecast_products": {
            "root": str(root),
            "restart_template": "restart.{mpas_valid_file_time}.nc",
            "state_template": "state.{mpas_valid_file_time}.nc",
        },
        "forecast": {
            "run_dir": "runs/{init_yyyymmddhh}",
            "argv": ["/bin/true"],
            **({"resources": resources} if resources is not None else {}),
        },
    }}}


def test_compiler_resolves_product_paths_and_abstract_resources(tmp_path: Path) -> None:
    """Scientific resource demand must reach the execution request unchanged."""
    stage = compile_mpas_forecast(
        _config(tmp_path, {"mpi_ranks": 128, "threads_per_rank": 1, "walltime": "01:00:00", "memory_mb": 8192}),
        workspace=tmp_path,
        init_time="2026-06-20T00:00:00Z",
        lead_hours=48,
        backend=LocalProcessBackend(),
    )
    assert stage.run_dir == tmp_path / "runs/2026062000"
    assert stage.product.valid_time == "2026-06-22_00:00:00"
    assert stage.request is not None
    assert stage.request.resources.mpi_ranks == 128
    assert stage.request.resources.threads_per_rank == 1
    assert stage.request.resources.walltime == "01:00:00"
    assert stage.request.resources.memory_mb == 8192


def test_compiler_rejects_platform_resource_keys_in_scientific_yaml(tmp_path: Path) -> None:
    """Queue or launcher syntax cannot be declared as MPAS resource demand."""
    with pytest.raises(MpasForecastConfigurationError, match="unsupported key"):
        compile_mpas_forecast(
            _config(tmp_path, {"mpi_ranks": 128, "queue": "pesqmini"}),
            workspace=tmp_path,
            init_time="2026-06-20T00:00:00Z",
            lead_hours=48,
            backend=LocalProcessBackend(),
        )
