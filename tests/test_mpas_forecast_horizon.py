from __future__ import annotations

from pathlib import Path

import pytest

from monan_jedi_workflow.mpas_stage import load_mpas_run
from monan_jedi_workflow.stage_config import StageConfigurationError


def _write_case(path: Path, *, lead_hours: int, run_hours: int) -> None:
    path.mkdir()
    (path / "mpas.yaml").write_text(
        f"""mpas:
  lead_hours: {lead_hours}
  run_dir: {path}/run/{{cycle_id}}
  forecast_contract:
    run_hours: {run_hours}
    da_state_interval_hours: 3
    mpi_ranks: 128
    partition: x1.10242.graph.info.part.128
    do_restart: false
    do_DAcycling: true
    IAU: 'off'
  links: []
  templates: []
  pbs:
    queue: pesqmidi
    select: 1
    ncpus: 128
    mpiprocs: 128
    walltime: '02:00:00'
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


def test_48_hour_integration_can_supply_six_hour_background_and_forecast(tmp_path: Path) -> None:
    case = tmp_path / "case"
    _write_case(case, lead_hours=48, run_hours=48)

    run = load_mpas_run(case, "2018-04-15T00:00:00Z")

    assert run.config["lead_hours"] == 48
    assert run.context["mpas_t_plus_3_file_time"] == "2018-04-15_03.00.00"
    assert run.context["mpas_valid_file_time"] == "2018-04-17_00.00.00"


def test_forecast_contract_run_hours_must_match_lead_hours(tmp_path: Path) -> None:
    case = tmp_path / "case"
    _write_case(case, lead_hours=48, run_hours=6)

    with pytest.raises(StageConfigurationError, match="run_hours"):
        load_mpas_run(case, "2018-04-15T00:00:00Z")
