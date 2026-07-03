"""Tests for safe V2 WPS-to-MPAS preparation-only preflight."""

from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner
from monan_jedi_workflow.platforms.local import LocalProcessBackend
from monan_jedi_workflow.workflows.nmc_campaign import build_nmc_campaign


def _write(path: Path, content: str = "input") -> Path:
    """Create one fixture input file and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_prepare_only_renders_wps_and_mpas_without_execution(tmp_path: Path) -> None:
    """Preflight stages static inputs and declared dangling upstream links only."""
    grib = _write(tmp_path / "inputs/gfs.grib2")
    vtable = _write(tmp_path / "inputs/Vtable.GFS")
    grid = _write(tmp_path / "inputs/x1.10242.grid.nc")
    partition = _write(tmp_path / "inputs/x1.10242.graph.info.part.128")
    geog = tmp_path / "inputs/geog"
    _write(geog / "topo_gmted2010_30s/index")
    streams = _write(
        tmp_path / "templates/streams.init_atmosphere",
        """<streams>
<immutable_stream name="input" filename_template="wrong-grid.nc" />
<immutable_stream name="output" filename_template="x1.40962.init.nc" />
</streams>""",
    )
    namelist = _write(
        tmp_path / "templates/namelist.init_atmosphere",
        """&nhyd_model
 config_init_case = 0
 config_start_time = '2000-01-01_00:00:00'
 config_stop_time = '2000-01-01_00:00:00'
 config_geog_data_path = '/glade/work/wrfhelp/WPS_GEOG/'
 config_met_prefix = 'UNKNOWN'
 config_fg_interval = 0
 config_block_decomp_file_prefix = 'x1.40962.graph.info.part.'
/
""",
    )
    wps_namelist = _write(tmp_path / "templates/namelist.wps", "prefix = 'FILE'\nstart_date = '{init_time}'\n")
    config = {
        "case": {"name": "preflight"},
        "model": {
            "wps": {
                "ungrib_products": {
                    "root": str(tmp_path / "workspace/wps"),
                    "intermediate_template": "{init_yyyymmddhh}/FILE:{wps_time}",
                },
                "ungrib": {
                    "run_dir": str(tmp_path / "workspace/wps/{init_yyyymmddhh}"),
                    "argv": ["/bin/false"],
                    "grib_inputs": [{"source": str(grib), "target": "GRIBFILE.AAA"}],
                    "links": [{"source": str(vtable), "target": "Vtable"}],
                    "templates": [{"source": str(wps_namelist), "target": "namelist.wps"}],
                },
            },
            "mpas": {
                "initialization_products": {
                    "root": str(tmp_path / "workspace/init-products"),
                    "state_template": "{init_yyyymmddhh}/init.nc",
                },
                "initialization": {
                    "run_dir": "runs/init/{init_yyyymmddhh}",
                    "argv": ["/bin/false"],
                    "wps_input": {"target": "FILE:{wps_time}"},
                    "geog_data_path": str(geog),
                    "geog_required_datasets": ["topo_gmted2010_30s"],
                    "links": [
                        {"source": str(grid), "target": "x1.10242.grid.nc"},
                        {"source": str(partition), "target": "x1.10242.graph.info.part.128"},
                    ],
                    "templates": [
                        {"source": str(streams), "target": "streams.init_atmosphere"},
                        {"source": str(namelist), "target": "namelist.init_atmosphere"},
                    ],
                },
                "forecast_products": {
                    "root": str(tmp_path / "workspace/forecast-products"),
                    "restart_template": "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
                    "state_template": "{init_yyyymmddhh}/f{lead_hours_03d}/state.{mpas_valid_file_time}.nc",
                },
                "forecast": {
                    "run_dir": "runs/forecast/{init_yyyymmddhh}/f{lead_hours_03d}",
                    "argv": ["/bin/false"],
                    "links": [{"source": "{initial_state}", "target": "init.nc"}],
                },
            },
        },
        "bmatrix": {
            "nmc_pairs": {
                "start_valid_time": "2026-06-22T00:00:00Z",
                "end_valid_time": "2026-06-25T00:00:00Z",
            }
        },
    }
    context = RunContext("bmatrix", "preflight", tmp_path / "workspace", config=config, prepare_only=True)
    plan = build_nmc_campaign(context, backend=LocalProcessBackend())
    results = LocalWorkflowRunner(plan.specification, plan.stages).run(context)

    assert len(results) == 19
    init = next(stage for stage in plan.initializations if stage.product.cycle_time == "2026-06-20_00:00:00")
    forecast = next(stage for stage in plan.forecasts if stage.product.init_time == "2026-06-20_00:00:00")
    assert (init.run_dir / "FILE:2026-06-20_00").is_symlink()
    assert not (init.run_dir / "FILE:2026-06-20_00").exists()
    assert (init.run_dir / "x1.10242.grid.nc").is_symlink()
    assert (init.run_dir / "x1.10242.graph.info.part.128").is_symlink()
    assert (forecast.run_dir / "init.nc").is_symlink()
    assert not (forecast.run_dir / "init.nc").exists()
    stream = (init.run_dir / "streams.init_atmosphere").read_text(encoding="utf-8")
    assert "x1.10242.grid.nc" in stream
    assert "FILE:2026-06-20_00" not in stream
    assert 'filename_template="init.nc"' in stream
    assert "x1.40962.init.nc" not in stream
    rendered = (init.run_dir / "namelist.init_atmosphere").read_text(encoding="utf-8")
    assert f"config_geog_data_path = '{geog}/'" in rendered
    assert "config_met_prefix = 'FILE'" in rendered
    assert "x1.10242.graph.info.part." in rendered
    assert not context.state_path.exists()
