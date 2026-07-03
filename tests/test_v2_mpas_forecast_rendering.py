"""Regression tests for cycle-specific MPAS forecast rendering."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from monan_jedi_workflow.components.model.mpas.forecast_config import compile_mpas_forecast
from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def test_forecast_prepare_replaces_historical_template_values(tmp_path: Path) -> None:
    """A 2018 source template must render as the configured 2026 f024 stage."""
    partition = tmp_path / "inputs/x1.10242.graph.info.part.128"
    partition.parent.mkdir(parents=True)
    partition.write_text("partition", encoding="utf-8")
    namelist = tmp_path / "templates/namelist.atmosphere"
    namelist.parent.mkdir(parents=True)
    namelist.write_text(
        """&nhyd_model
 config_start_time = '2018-04-15_00:00:00'
 config_stop_time = '2018-04-17_00:00:00'
 config_block_decomp_file_prefix = 'x1.40962.graph.info.part.'
 config_do_restart = true
/
""",
        encoding="utf-8",
    )
    streams = tmp_path / "templates/streams.atmosphere"
    streams.write_text(
        '<streams><stream name="input" type="input" filename_template="old.init.nc" input_interval="initial_only" /></streams>',
        encoding="utf-8",
    )
    initial_state = tmp_path / "products/init/2026062100/init.nc"
    config = {
        "model": {
            "mpas": {
                "forecast_products": {
                    "root": str(tmp_path / "products/forecast"),
                    "restart_template": "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
                    "state_template": "{init_yyyymmddhh}/f{lead_hours_03d}/state.{mpas_valid_file_time}.nc",
                },
                "forecast": {
                    "run_dir": "runs/forecast/{init_yyyymmddhh}/f{lead_hours_03d}",
                    "argv": ["/bin/false"],
                    "links": [
                        {"source": "{initial_state}", "target": "init.nc"},
                        {"source": str(partition), "target": "x1.10242.graph.info.part.128"},
                    ],
                    "templates": [
                        {"source": str(namelist), "target": "namelist.atmosphere"},
                        {"source": str(streams), "target": "streams.atmosphere"},
                    ],
                },
            }
        }
    }
    context = RunContext("bmatrix", "forecast-render", tmp_path, config=config, prepare_only=True)
    stage = compile_mpas_forecast(
        config,
        workspace=tmp_path,
        init_time="2026-06-21T00:00:00Z",
        lead_hours=24,
        backend=LocalProcessBackend(),
        extra_values={"initial_state": str(initial_state)},
    )
    stage.prepare(context)

    text = (stage.run_dir / "namelist.atmosphere").read_text(encoding="utf-8")
    assert "config_start_time = '2026-06-21_00:00:00'" in text
    assert "config_stop_time = '2026-06-22_00:00:00'" in text
    assert "config_block_decomp_file_prefix = 'x1.10242.graph.info.part.'" in text
    assert "config_do_restart = false" in text
    assert "2018-04-15" not in text
    assert "x1.40962" not in text

    root = ElementTree.parse(stage.run_dir / "streams.atmosphere").getroot()
    stream = next(item for item in root.iter() if item.get("name") == "input")
    assert stream.get("filename_template") == "init.nc"
    assert stream.get("input_interval") == "initial_only"
    assert (stage.run_dir / "init.nc").is_symlink()
    assert not (stage.run_dir / "init.nc").exists()
