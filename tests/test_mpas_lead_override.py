from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.mpas_stage import load_mpas_run, prepare_mpas


def test_mpas_lead_override_changes_context_and_run_directory(tmp_path: Path) -> None:
    config = tmp_path / "case"
    config.mkdir()
    executable = config / "mpas_atmosphere"
    executable.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    executable.chmod(0o755)
    (config / "mpas.yaml").write_text(
        """mpas:
  lead_hours: 6
  run_dir: work/{cycle_id}/f{lead_hours}
  links:
    - source: mpas_atmosphere
      target: mpas_atmosphere
  templates: []
  pbs:
    queue: debug
    walltime: "00:05:00"
    ncpus: 1
    mpiprocs: 1
    launcher: mpiexec
    command: [./mpas_atmosphere]
    environment: {}
  validation:
    required_outputs: [mpasout.{mpas_valid_file_time}.nc]
    required_log_markers: [complete]
""",
        encoding="utf-8",
    )

    run = load_mpas_run(config, "2018-04-15T00:00:00Z", lead_hours=48)
    prepared = prepare_mpas(config, "2018-04-15T00:00:00Z", lead_hours=48)

    assert run.run_dir == config / "work/20180415T000000Z/f48"
    assert run.context["mpas_valid_time"] == "2018-04-17_00:00:00"
    assert prepared.manifest_path.is_file()
    assert "lead=48h" not in prepared.pbs_path.read_text()
