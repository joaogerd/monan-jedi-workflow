from __future__ import annotations

import json
import sys
from pathlib import Path

from monan_jedi_workflow.wps_stage import prepare_wps, run_wps, validate_wps


def test_wps_stage_converts_declared_input_and_validates(tmp_path: Path) -> None:
    input_file = tmp_path / "input.grib2"
    input_file.write_bytes(b"grib")
    template = tmp_path / "namelist.wps.in"
    template.write_text("start = '{wps_time}'\n", encoding="utf-8")
    config = tmp_path / "case"
    config.mkdir()

    link_code = (
        "from pathlib import Path; import sys; "
        "Path('GRIBFILE.AAA').symlink_to(Path(sys.argv[1]))"
    )
    ungrib_code = (
        "from pathlib import Path; "
        "assert Path('GRIBFILE.AAA').is_file(); "
        "Path('FILE:2018-04-15_00').write_bytes(b'wps'); "
        "print('complete')"
    )
    (config / "wps.yaml").write_text(
        f"""wps:
  variables:
    root: {tmp_path}/work
    input: {input_file}
    python: {sys.executable}
  work_dir: "{{root}}/{{cycle_yyyymmddhh}}"
  templates:
    - {{source: {template}, target: namelist.wps}}
  run:
    link_grib_argv: ["{{python}}", -c, {json.dumps(link_code)}, "{{input}}"]
    ungrib_argv: ["{{python}}", -c, {json.dumps(ungrib_code)}]
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

    work = tmp_path / "work" / "2018041500"
    assert (work / "FILE:2018-04-15_00").read_bytes() == b"wps"
    assert report.is_file()
