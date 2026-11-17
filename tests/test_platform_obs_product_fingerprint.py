"""Regression: produced Obs2IODA files must not become new stage inputs."""
from pathlib import Path
from types import SimpleNamespace

import monan_jedi_workflow.platform_cli as cli
import monan_jedi_workflow.platform_backend as backend
import monan_jedi_workflow.obs2ioda_stage as obs


def test_observation_outputs_never_change_input_fingerprint(tmp_path, monkeypatch):
    source = tmp_path / "prepbufr.bufr"
    source.write_text("raw observation")
    converter = tmp_path / "converter"
    converter.write_text("#! native converter")
    inspection = tmp_path / "inspector"
    inspection.write_text("#! native inspector")
    output = tmp_path / "output.h5"

    plan = {"converters": [{
        "name": "conventional",
        "inputs": [str(source)],
        "outputs": [str(output)],
        "argv": [str(converter), str(source), str(output)],
    }]}
    run = SimpleNamespace(
        config={"links": [], "templates": [], "link_directories": []},
        config_dir=tmp_path,
        context={},
        work_dir=tmp_path,
    )
    op = SimpleNamespace(key="obs2ioda", section={}, domain_file=tmp_path / "obs.yaml", identity="fixture")
    request = SimpleNamespace(cycle="2025-09-01T00:00:00Z")
    monkeypatch.setattr(backend, "materialize", lambda _op, d: d)
    monkeypatch.setattr(backend, "render_run", lambda _op, _request, _dir: run)
    monkeypatch.setattr(obs, "_build_plan", lambda _run: plan)
    import monan_jedi_workflow.obs_cycle_stage as cycle_stage
    monkeypatch.setattr(cycle_stage, "_resolve_plan", lambda _run, p: (p, []))
    monkeypatch.setattr(obs, "_render_inspection", lambda *args: {
        "argv": [str(inspection), str(output)],
    })

    before = cli.input_records(cli.inspect_native(op, request, tmp_path))
    output.write_text("an IODA product")
    after = cli.input_records(cli.inspect_native(op, request, tmp_path))
    assert before == after
    assert str(output) not in [
        item["path"] for item in after
    ] if after else True
