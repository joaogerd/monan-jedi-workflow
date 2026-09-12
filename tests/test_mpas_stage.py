from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.mpas_pipeline import build_plan, load_pipeline_run, validate_contract
from monan_jedi_workflow.mpas_stage import prepare_mpas, submit_mpas


REPOSITORY = Path(__file__).resolve().parents[1]


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
    assert pbs.count("#PBS -l place=excl") == 1
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


def test_cycling_contract_renders_128_rank_6h_forecast_and_both_da_states(tmp_path: Path) -> None:
    config = tmp_path / "case"
    config.mkdir()
    initial = config / "analysis-full.nc"
    executable = config / "mpas_atmosphere"
    initial.write_bytes(b"full")
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    assets = config / "assets"
    assets.mkdir()
    (assets / "RRTMG_LW_DATA").write_bytes(b"table")
    namelist = config / "namelist.in"
    streams = config / "streams.in"
    namelist.write_text("duration={mpas_run_duration}\n", encoding="utf-8")
    streams.write_text("interval=03:00:00\n", encoding="utf-8")
    (config / "mpas.yaml").write_text(
        f"""mpas:
  lead_hours: 6
  run_dir: {config}/run/{{cycle_id}}
  forecast_contract:
    run_hours: 6
    da_state_interval_hours: 3
    mpi_ranks: 128
    partition: x1.10242.graph.info.part.128
    do_restart: false
    do_DAcycling: true
    IAU: 'off'
  link_directories: [{assets}]
  links:
    - {{source: {initial}, target: mpas.analysis-full.2018-04-15_00.00.00.nc}}
    - {{source: {executable}, target: mpas_atmosphere}}
  templates:
    - {{source: {namelist}, target: namelist.atmosphere}}
    - {{source: {streams}, target: streams.atmosphere}}
  pbs:
    queue: pesqmidi
    select: 1
    ncpus: 128
    mpiprocs: 128
    walltime: '02:00:00'
    launcher: /opt/cray/pals/1.6/bin/mpiexec
    setup: [/path/load_jaci_env.sh]
    command: [./mpas_atmosphere]
  validation:
    log: log.atmosphere.0000.out
    required_log_markers: [Finished]
    required_outputs:
      - mpasout.{{mpas_t_plus_3_file_time}}.nc
      - mpasout.{{mpas_valid_file_time}}.nc
""",
        encoding="utf-8",
    )
    run = prepare_mpas(config, "2018-04-15T00:00:00Z")
    pbs = run.pbs_path.read_text()
    assert "#PBS -q pesqmidi" in pbs
    assert "#PBS -l select=1:ncpus=128:mpiprocs=128" in pbs
    assert pbs.count("#PBS -l place=excl") == 1
    assert "source /path/load_jaci_env.sh" in pbs
    assert "mpiexec -n 128 ./mpas_atmosphere" in pbs
    assert (run.run_dir / "RRTMG_LW_DATA").is_symlink()
    assert (run.run_dir / "namelist.atmosphere").read_text() == "duration=0_06:00:00\n"
    assert run.context["mpas_t_plus_3_file_time"] == "2018-04-15_03.00.00"
    assert run.context["mpas_valid_file_time"] == "2018-04-15_06.00.00"


def test_repeated_submit_does_not_create_duplicate_pbs_job(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "case"
    config.mkdir()
    executable = config / "mpas_atmosphere"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    (config / "mpas.yaml").write_text(
        f"""mpas:
  lead_hours: 1
  run_dir: {config}/run/{{cycle_id}}
  links: [{{source: {executable}, target: mpas_atmosphere}}]
  pbs:
    queue: test
    mpiprocs: 1
    walltime: '00:10:00'
    command: [./mpas_atmosphere]
  validation:
    log: log
    required_log_markers: [done]
    required_outputs: [output.nc]
""",
        encoding="utf-8",
    )
    prepare_mpas(config, "2018-04-15T00:00:00Z")
    calls = []

    class Result:
        returncode = 0
        stdout = "123.jaci\n"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Result()

    monkeypatch.setattr("monan_jedi_workflow.mpas_stage.subprocess.run", fake_run)
    assert submit_mpas(config, "2018-04-15T00:00:00Z") == "123.jaci"
    assert submit_mpas(config, "2018-04-15T00:00:00Z") == "123.jaci"
    assert len(calls) == 1


def test_new_submission_archives_previous_logs_without_touching_products(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "case"
    config.mkdir()
    executable = config / "mpas_atmosphere"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    (config / "mpas.yaml").write_text(
        f"""mpas:
  lead_hours: 1
  run_dir: {config}/run/{{cycle_id}}
  links: [{{source: {executable}, target: mpas_atmosphere}}]
  pbs:
    queue: test
    mpiprocs: 1
    walltime: '00:10:00'
    command: [./mpas_atmosphere]
  validation:
    log: log.atmosphere.0000.out
    required_log_markers: [done]
    required_outputs: [mpasout.nc]
""",
        encoding="utf-8",
    )
    run = prepare_mpas(config, "2018-04-15T00:00:00Z")
    stale = run.run_dir / "log.atmosphere.0000.err"
    stale.write_text("CRITICAL ERROR from failed attempt\n", encoding="utf-8")
    product = run.run_dir / "mpasout.nc"
    product.write_bytes(b"scientific state")

    class Result:
        returncode = 0
        stdout = "456.jaci\n"
        stderr = ""

    monkeypatch.setattr(
        "monan_jedi_workflow.mpas_stage.subprocess.run", lambda *args, **kwargs: Result()
    )
    assert submit_mpas(config, "2018-04-15T00:00:00Z") == "456.jaci"
    assert not stale.exists()
    archives = list((run.run_dir / ".monan-jedi-workflow/previous-logs").glob("*/log.atmosphere.0000.err"))
    assert len(archives) == 1
    assert "failed attempt" in archives[0].read_text(encoding="utf-8")
    assert product.read_bytes() == b"scientific state"


def test_jaci_cycling_templates_pin_scientific_forecast_contract() -> None:
    template_dir = REPOSITORY / "examples/simpleworkflow/cycled_da/templates"
    namelist = (template_dir / "namelist.atmosphere.cycling.in").read_text()
    streams = (template_dir / "streams.atmosphere.cycling.in").read_text()
    assert "config_run_duration = '{mpas_run_duration}'" in namelist
    assert "config_do_restart = .false." in namelist
    assert "config_do_DAcycling = .true." in namelist
    assert "config_IAU_option = 'off'" in namelist
    assert 'name="da_state"' in streams
    assert 'output_interval="03:00:00"' in streams
    assert 'name="restart" type="output"' in streams
    assert 'output_interval="24:00:00"' in streams
