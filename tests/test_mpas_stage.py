from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.mpas_pipeline import build_plan, load_pipeline_run, validate_contract
from monan_jedi_workflow.mpas_stage import prepare_mpas


def test_prepare_mpas_stages_links_templates_and_pbs(tmp_path: Path) -> None:
    config_dir = tmp_path / "experiment"
    (config_dir / "inputs").mkdir(parents=True)
    (config_dir / "templates").mkdir()
    (config_dir / "inputs/init.nc").write_bytes(b"init")
    executable = config_dir / "inputs/mpas_atmosphere"
    executable.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    executable.chmod(0o755)
    (config_dir / "templates/namelist.atmosphere.in").write_text(
        "config_start_time = '{mpas_time}'\nconfig_run_duration = '{lead_hours}:00:00'\n",
        encoding="utf-8",
    )
    (config_dir / "templates/streams.atmosphere.in").write_text(
        "output at {mpas_valid_time}\n", encoding="utf-8"
    )
    (config_dir / "mpas.yaml").write_text(
        """mpas:
  lead_hours: 6
  run_dir: work/mpas/{cycle_id}
  clean_patterns: ["mpasout.*.nc"]
  links:
    - source: inputs/init.nc
      target: init.nc
    - source: inputs/mpas_atmosphere
      target: mpas_atmosphere
  templates:
    - source: templates/namelist.atmosphere.in
      target: namelist.atmosphere
    - source: templates/streams.atmosphere.in
      target: streams.atmosphere
  pbs:
    filename: run_mpas.pbs
    job_name: mpas_test
    queue: pesqmini
    select: 1
    ncpus: 2
    mpiprocs: 2
    walltime: "00:10:00"
    launcher: mpiexec
    command: ["./mpas_atmosphere"]
    environment:
      OMP_NUM_THREADS: "1"
  validation:
    log: stdout.log
    required_log_markers: ["MPAS complete"]
    required_outputs: ["mpasout.{mpas_valid_time}.nc"]
""",
        encoding="utf-8",
    )

    run = prepare_mpas(config_dir, "2018-04-15T00:00:00Z")

    assert run.run_dir == config_dir / "work/mpas/20180415T000000Z"
    assert (run.run_dir / "init.nc").is_symlink()
    assert (run.run_dir / "mpas_atmosphere").is_symlink()
    assert "2018-04-15_00:00:00" in (run.run_dir / "namelist.atmosphere").read_text()
    assert "2018-04-15_06:00:00" in (run.run_dir / "streams.atmosphere").read_text()
    pbs = run.pbs_path.read_text()
    assert "#PBS -q pesqmini" in pbs
    assert "mpiexec -n 2 ./mpas_atmosphere" in pbs


def test_high_level_pipeline_selects_wps_and_validates_local_assets(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh.nc"
    initial = tmp_path / "init.2018041500.nc"
    mesh.write_bytes(b"mesh")
    initial.write_bytes(b"init")
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        f"""pipeline:
  work_root: {tmp_path}/work
  forecast_hours: 6
  inputs:
    assets:
      - name: initial
        provider: local
        path: {tmp_path}/init.{{cycle_yyyymmddhh}}.nc
  static:
    assets:
      mesh: {mesh}
  stages:
    mode: forecast
    wps: false
""",
        encoding="utf-8",
    )
    run = load_pipeline_run(config, "2018-04-15T00:00:00Z")
    assert validate_contract(run)["valid"] is True
    plan = build_plan(run)
    assert [item.name for item in plan] == ["inputs", "static", "wps", "mpas_init", "mpas_forecast"]
    assert plan[2].enabled is False
