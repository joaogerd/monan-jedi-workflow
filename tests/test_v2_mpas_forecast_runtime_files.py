"""Tests for declared MPAS atmosphere runtime support files."""

from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.components.model.mpas import compile_mpas_forecast
from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def _write(path: Path, content: str = "input") -> Path:
    """Create one test input and return its absolute path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_forecast_preparation_stages_declared_atmosphere_runtime_files(tmp_path: Path) -> None:
    """Ozone tables from core_atmosphere must be present before a forecast starts."""
    initial = _write(tmp_path / "inputs/init.nc")
    partition = _write(tmp_path / "inputs/x1.10242.graph.info.part.128")
    support = tmp_path / "core_atmosphere"
    for name in ("OZONE_PLEV.TBL", "OZONE_LAT.TBL", "OZONE_DAT.TBL", "LANDUSE.TBL"):
        _write(support / name, name)
    _write(support / "namelist.atmosphere", "installed template")
    _write(support / "streams.atmosphere", "installed template")
    namelist = _write(
        tmp_path / "templates/namelist.atmosphere",
        """&nhyd_model
 config_start_time = '2000-01-01_00:00:00'
 config_run_duration = '0_00:00:00'
 config_do_restart = true
 config_block_decomp_file_prefix = 'x1.40962.graph.info.part.'
/
""",
    )
    streams = _write(
        tmp_path / "templates/streams.atmosphere",
        '<streams><immutable_stream name="input" type="input" filename_template="wrong.nc" /></streams>',
    )
    config = {
        "model": {
            "mpas": {
                "forecast_products": {
                    "root": str(tmp_path / "products"),
                    "restart_template": "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
                    "state_template": "{init_yyyymmddhh}/f{lead_hours_03d}/mpasout.{mpas_valid_file_time}.nc",
                },
                "forecast": {
                    "run_dir": "runs/forecast/{init_yyyymmddhh}/f{lead_hours_03d}",
                    "argv": ["/bin/true"],
                    "runtime_files": {
                        "source_dir": str(support),
                        "exclude": ["namelist.atmosphere", "streams.atmosphere"],
                    },
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
    context = RunContext("bmatrix", "forecast-runtime-files", tmp_path, config=config)
    stage = compile_mpas_forecast(
        config,
        workspace=tmp_path,
        init_time="2026-06-20T00:00:00Z",
        lead_hours=48,
        backend=LocalProcessBackend(),
        extra_values={"initial_state": str(initial)},
    )

    stage.validate_inputs(context).require_valid()
    stage.prepare(context)

    for name in ("OZONE_PLEV.TBL", "OZONE_LAT.TBL", "OZONE_DAT.TBL", "LANDUSE.TBL"):
        assert (stage.run_dir / name).is_symlink()
        assert (stage.run_dir / name).resolve() == support / name
    assert not (stage.run_dir / "namelist.atmosphere").is_symlink()
    assert not (stage.run_dir / "streams.atmosphere").is_symlink()
