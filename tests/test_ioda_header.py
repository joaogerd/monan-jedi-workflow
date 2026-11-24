"""Portable IODA validation when a clean login environment lacks ncdump."""
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

from monan_jedi_workflow.ioda_header import inspect_header, main
from monan_jedi_workflow.obs2ioda_stage import _render_inspection


def test_netcdf_header_inspects_actual_ioda_groups(tmp_path):
    netcdf4 = pytest.importorskip("netCDF4")
    output = tmp_path / "ioda.nc"
    with netcdf4.Dataset(str(output), "w", format="NETCDF4") as file:
        file.createDimension("Location", 1)
        for name in ("MetaData", "ObsValue", "ObsError", "PreQC"):
            group = file.createGroup(name)
            group.createVariable("test", "f4", ("Location",))
    rendered = "\n".join(inspect_header(output))
    assert all(f"group: /{name}" in rendered for name in
               ("MetaData", "ObsValue", "ObsError", "PreQC"))
    completed = subprocess.run(
        [sys.executable, "-m", "monan_jedi_workflow.ioda_header", str(output)],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ObsValue" in completed.stdout


def test_netcdf_header_rejects_invalid_file(tmp_path, capsys):
    output = tmp_path / "corrupt.h5"
    output.write_bytes(b"not a netcdf file")
    assert main([str(output)]) == 1
    assert "IODA INSPECTION ERROR" in capsys.readouterr().err


def test_configured_default_ncdump_falls_back_only_when_missing(monkeypatch):
    import monan_jedi_workflow.obs2ioda_stage as stage
    run = SimpleNamespace(
        config={"inspection": {
            "argv": ["ncdump", "-h", "{output}"],
            "required_header_markers": ["ObsValue"],
        }},
        context={},
    )
    converter = {"name": "gpsro", "validation": {}}
    output = Path("/tmp/ioda-example.h5")
    monkeypatch.setattr(stage.shutil, "which", lambda name: None)
    result = _render_inspection(run, converter, output)
    assert result["argv"] == [
        sys.executable, "-m", "monan_jedi_workflow.ioda_header", str(output)
    ]
    assert result["required_header_markers"] == ["ObsValue"]
    monkeypatch.setattr(stage.shutil, "which", lambda name: "/usr/bin/ncdump")
    result = _render_inspection(run, converter, output)
    assert result["argv"] == ["ncdump", "-h", str(output)]


def test_explicit_custom_inspector_is_not_replaced(monkeypatch):
    import monan_jedi_workflow.obs2ioda_stage as stage
    run = SimpleNamespace(
        config={"inspection": {"argv": ["/custom/ncdump", "-h", "{output}"]}},
        context={},
    )
    monkeypatch.setattr(stage.shutil, "which", lambda name: None)
    result = _render_inspection(
        run, {"name": "custom", "validation": {}}, Path("/tmp/example.h5")
    )
    assert result["argv"][0] == "/custom/ncdump"
