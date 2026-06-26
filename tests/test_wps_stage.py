from __future__ import annotations

from pathlib import Path

from monan_jedi_workflow.wps_stage import prepare_wps, run_wps, validate_wps


def _executable(path: Path, content: str) -> None:
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + content, encoding="utf-8")
    path.chmod(0o755)


def test_wps_stage_converts_declared_input_and_validates(tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    input_file = tmp_path / "input.grib2"
    input_file.write_bytes(b"grib")
    link = tools / "link_grib.csh"
    ungrib = tools / "ungrib.exe"
    vtable = tools / "Vtable.GFS"
    vtable.write_text("vtable\n", encoding="utf-8")
    _executable(link, "ln -sfn \"$1\" GRIBFILE.AAA\n")
    _executable(ungrib, "test -r GRIBFILE.AAA\nprintf 'wps' > FILE:2018-04-15_00\nprintf 'complete\n'\n")
    template = tmp_path / "namelist.wps.in"
    template.write_text("start = '{wps_time}'\n", encoding="utf-8")
    config = tmp_path / "case"
    config.mkdir()
    (config / "wps.yaml").write_text(
        f"""wps:
  variables:
    root: {tmp_path}/work
    input: {input_file}
  work_dir: "{{root}}/{{cycle_yyyymmddhh}}"
  links:
    - {{source: {link}, target: link_grib.csh}}
    - {{source: {ungrib}, target: ungrib.exe}}
    - {{source: {vtable}, target: Vtable}}
  templates:
    - {{source: {template}, target: namelist.wps}}
  run:
    link_grib_argv: [./link_grib.csh, "{{input}}"]
    ungrib_argv: [./ungrib.exe]
  validation:
    log: logs/ungrib.stdout.log
    required_log_markers: [complete]
    required_outputs: ["{{work_dir}}/FILE:{{wps_time}}"]
""",
        encoding="utf-8",
    )

    prepare_wps(config, "2018-04-15T00:00:00Z")
    run_wps(config, "2018-04-15T00:00:00Z")
    report = validate_wps(config, "2018-04-15T00:00:00Z")

    work = tmp_path / "work" / "20180415T000000Z"
    assert (work / "FILE:2018-04-15_00").read_bytes() == b"wps"
    assert report.is_file()
