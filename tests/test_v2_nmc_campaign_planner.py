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
        "bmatrix": {"nmc_pairs": {"start_valid_time": "2026-06-22T00:00:00Z", "end_valid_time": "2026-06-25T00:00:00Z"}},
    }
    context = RunContext("bmatrix", "campaign", tmp_path / "workspace", config=config)
    plan = build_nmc_campaign(context, backend=LocalProcessBackend())

    initial_by_time = {stage.product.cycle_time: stage.product.state for stage in plan.initializations}
    assert len(plan.initializations) == 5
    assert len(plan.forecasts) == 8
    assert len(plan.specification.stages) == 14
    for forecast in plan.forecasts:
        assert forecast.links[0].source == initial_by_time[forecast.product.init_time]
        assert plan.specification.stage(forecast.spec.name).needs == (next(stage.spec.name for stage in plan.initializations if stage.product.cycle_time == forecast.product.init_time),)


def test_nmc_campaign_wires_wps_file_products_to_matching_initializations(tmp_path: Path) -> None:
    """WPS FILE artifacts must be explicit init inputs and scheduler dependencies."""
    grib = tmp_path / "gfs.grib2"
    grib.write_bytes(b"grib")
    partition = tmp_path / "x1.10242.graph.info.part.128"
    partition.write_text("partition", encoding="utf-8")
    config = {
        "model": {
            "wps": {
                "ungrib_products": {"root": str(tmp_path / "wps"), "intermediate_template": "{init_yyyymmddhh}/FILE:{wps_time}"},
                "ungrib": {"run_dir": str(tmp_path / "wps" / "{init_yyyymmddhh}"), "argv": ["/bin/true"], "grib_inputs": [{"source": str(grib), "target": "GRIBFILE.AAA"}]},
            },
            "mpas": {
                "initialization_products": {"root": str(tmp_path / "init"), "state_template": "{init_yyyymmddhh}/init.nc"},
                "initialization": {
                    "run_dir": "runs/init/{init_yyyymmddhh}", "argv": ["/bin/true"], "wps_input": {"target": "FILE:{wps_time}"},
                    "links": [{"source": str(partition), "target": "x1.10242.graph.info.part.128"}],
                },
                "forecast_products": {"root": str(tmp_path / "forecast"), "restart_template": "restart.{mpas_valid_file_time}.nc", "state_template": "state.{mpas_valid_file_time}.nc"},
                "forecast": {"run_dir": "runs/forecast/{init_yyyymmddhh}/f{lead_hours_03d}", "argv": ["/bin/true"], "links": [{"source": "{initial_state}", "target": "initial_state.nc"}]},
            },
        },
        "bmatrix": {"nmc_pairs": {"start_valid_time": "2026-06-22T00:00:00Z", "end_valid_time": "2026-06-25T00:00:00Z"}},
    }
    context = RunContext("bmatrix", "campaign", tmp_path / "workspace", config=config)
    plan = build_nmc_campaign(context, backend=LocalProcessBackend())

    assert len(plan.wps_ungrib) == 5
    assert len(plan.specification.stages) == 19
    by_time = {stage.product.init_time: stage for stage in plan.wps_ungrib}
    for initialization in plan.initializations:
        forcing = by_time[initialization.product.cycle_time]
        assert initialization.links[-1].source == forcing.product.intermediate
        assert initialization.links[-1].target.name == f"FILE:{forcing.product.wps_time}"
        assert initialization.values["decomposition_prefix"] == "x1.10242.graph.info.part."
        assert plan.specification.stage(initialization.spec.name).needs == (forcing.spec.name,)