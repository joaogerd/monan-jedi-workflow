from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.init_stage import prepare_mpas_init


def test_mpas_init_prepare_stages_cycle_inputs_and_pbs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in ("mpas_init_atmosphere", "x1.10242.grid.nc", "x1.10242.graph.info", "x1.10242.graph.info.part.2", "FILE:2018-04-15_00"):
        path = source / name
        path.write_text(name, encoding="utf-8")
        if name == "mpas_init_atmosphere":
            path.chmod(0o755)
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "namelist.in").write_text("start='{mpas_time}'\n", encoding="utf-8")
    (templates / "streams.in").write_text("<streams/>\n", encoding="utf-8")
    case = tmp_path / "case"
    case.mkdir()
    (case / "mpas_init.yaml").write_text(
        f"""mpas_init:
  variables:
    root: {tmp_path}/work
  run_dir: "{{root}}/{{cycle_yyyymmddhh}}"
  links:
    - {{source: {source / 'mpas_init_atmosphere'}, target: mpas_init_atmosphere}}
    - {{source: {source / 'x1.10242.grid.nc'}, target: x1.10242.grid.nc}}
    - {{source: {source / 'x1.10242.graph.info'}, target: x1.10242.graph.info}}
    - {{source: {source / 'x1.10242.graph.info.part.2'}, target: x1.10242.graph.info.part.2}}
    - {{source: "{source / 'FILE:2018-04-15_00'}", target: "FILE:2018-04-15_00"}}
  templates:
    - {{source: {templates / 'namelist.in'}, target: namelist.init_atmosphere}}
    - {{source: {templates / 'streams.in'}, target: streams.init_atmosphere}}
  pbs:
    queue: pesqmini
    ncpus: 2
    mpiprocs: 2
    walltime: "00:10:00"
    launcher: mpiexec
    command: [./mpas_init_atmosphere]
""",
        encoding="utf-8",
    )

    run = prepare_mpas_init(case, "2018-04-15T00:00:00Z")

    assert (run.run_dir / "mpas_init_atmosphere").is_symlink()
    assert (run.run_dir / "FILE:2018-04-15_00").is_symlink()
    assert "2018-04-15_00:00:00" in (run.run_dir / "namelist.init_atmosphere").read_text()
    assert "#PBS -l select=1:ncpus=2:mpiprocs=2" in run.pbs_path.read_text()
