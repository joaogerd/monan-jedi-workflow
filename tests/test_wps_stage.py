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



def test_repeated_wps_prepare_never_removes_existing_scientific_output(tmp_path):
    import pytest
    from monan_jedi_workflow.wps_stage import load_wps_run
    config = tmp_path / "case"
    config.mkdir()
    (config / "wps.yaml").write_text(
        "wps:\n"
        "  work_dir: 'work/{cycle_id}'\n"
        "  clean_patterns: ['GFS:*']\n"
        "  run:\n"
        "    link_grib_argv: [echo, link]\n"
        "    ungrib_argv: [echo, ungrib]\n"
        "  validation:\n"
        "    required_outputs: ['{work_dir}/GFS:2026-01-29_18']\n"
    )
    cycle = "2026-01-29T18:00:00Z"
    run = load_wps_run(config, cycle)
    run.work_dir.mkdir(parents=True)
    output = run.work_dir / "GFS:2026-01-29_18"
    output.write_bytes(b"validated previous scientific output")
    run.manifest_path.parent.mkdir(parents=True)
    previous = '{"state":"completed","job_id":"829161.pbs-ha"}\n'
    run.manifest_path.write_text(previous)
    with pytest.raises(FileExistsError, match="refusing a second preparation"):
        prepare_wps(config, cycle)
    assert output.read_bytes() == b"validated previous scientific output"
    assert run.manifest_path.read_text() == previous


def test_wps_prepare_guards_orphaned_pbs_script_without_manifest(tmp_path):
    import pytest
    from monan_jedi_workflow.wps_stage import load_wps_run
    config = tmp_path / "case"
    config.mkdir()
    (config / "wps.yaml").write_text(
        "wps:\n"
        "  work_dir: 'work/{cycle_id}'\n"
        "  clean_patterns: ['GFS:*']\n"
    )
    cycle = "2026-01-29T18:00:00Z"
    run = load_wps_run(config, cycle)
    run.work_dir.mkdir(parents=True)
    output = run.work_dir / "GFS:2026-01-29_18"
    output.write_bytes(b"do-not-delete")
    script = run.work_dir / f"wps_{run.cycle.cycle_id}.native.pbs"
    script.write_text("#PBS previous job\n")
    with pytest.raises(FileExistsError, match="persistent state"):
        prepare_wps(config, cycle)
    assert output.read_bytes() == b"do-not-delete"
    assert script.is_file()
    assert not run.manifest_path.exists()
