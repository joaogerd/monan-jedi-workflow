"""Tests for the V2 executable NMC campaign planner."""

from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.platforms.local import LocalProcessBackend
from monan_jedi_workflow.workflows.nmc_campaign import build_nmc_campaign


def test_nmc_campaign_planner_wires_initial_states_to_forecasts(tmp_path: Path) -> None:
    """Each compiled forecast must receive the exact initial-state producer path."""
    config = {
        "model": {
            "mpas": {
                "initialization_products": {
                    "root": str(tmp_path / "initial-products"),
                    "state_template": "{init_yyyymmddhh}/init.{mpas_valid_file_time}.nc",
                },
                "initialization": {
                    "run_dir": "runs/init/{init_yyyymmddhh}",
                    "argv": ["/bin/true"],
                },
                "forecast_products": {
                    "root": str(tmp_path / "forecast-products"),
                    "restart_template": "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
                    "state_template": "{init_yyyymmddhh}/f{lead_hours_03d}/mpasout.{mpas_valid_file_time}.nc",
                },
                "forecast": {
                    "run_dir": "runs/forecast/{init_yyyymmddhh}/f{lead_hours_03d}",
                    "argv": ["/bin/true"],
                    "links": [{"source": "{initial_state}", "target": "initial_state.nc"}],
                },
            }
        },
        "bmatrix": {
            "nmc_pairs": {
                "start_valid_time": "2026-06-22T00:00:00Z",
                "end_valid_time": "2026-06-25T00:00:00Z",
            }
        },
    }
    context = RunContext("bmatrix", "campaign", tmp_path / "workspace", config=config)
    plan = build_nmc_campaign(context, backend=LocalProcessBackend())

    initial_by_time = {stage.product.cycle_time: stage.product.state for stage in plan.initializations}
    assert len(plan.initializations) == 5
    assert len(plan.forecasts) == 8
    assert len(plan.specification.stages) == 14
    for forecast in plan.forecasts:
        assert forecast.links[0].source == initial_by_time[forecast.product.init_time]
        assert plan.specification.stage(forecast.spec.name).needs == (
            next(stage.spec.name for stage in plan.initializations if stage.product.cycle_time == forecast.product.init_time),
        )
