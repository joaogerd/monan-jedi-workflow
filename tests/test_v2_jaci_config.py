"""Tests for V2 JACI backend configuration."""

from __future__ import annotations

from monan_jedi_workflow.platforms.jaci_backend import JaciPbsBackend
from monan_jedi_workflow.platforms.jaci_config import jaci_backend_factory


def test_jaci_backend_factory_uses_stage_specific_resources() -> None:
    """Initialization and forecast profiles must remain independently configurable."""
    config = {
        "platform": {
            "jaci": {
                "pbs": {
                    "common": {"prelude": ["module load test"], "poll_seconds": 15},
                    "initialization": {"queue": "pesqmini", "walltime": "00:20:00", "ncpus": 64, "mpiprocs": 64},
                    "forecast": {"queue": "pesqmidi", "walltime": "01:00:00", "ncpus": 128, "mpiprocs": 128},
                }
            }
        }
    }
    init = jaci_backend_factory(config, stage_kind="initialization")("mpas_init_test")
    forecast = jaci_backend_factory(config, stage_kind="forecast")("mpas_forecast_test")

    assert isinstance(init, JaciPbsBackend)
    assert init.resources.queue == "pesqmini"
    assert init.resources.ncpus == 64
    assert forecast.resources.queue == "pesqmidi"
    assert forecast.resources.mpiprocs == 128
    assert init.resources.job_name == "mpas_init_test"
