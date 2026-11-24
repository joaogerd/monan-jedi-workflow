"""Contract tests: controller Python only on login; native commands in PBS."""
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from monan_jedi_workflow import platform_backend
from monan_jedi_workflow.native_pbs import native_pbs_run


@pytest.mark.parametrize("key,module_name,submit_name", [
    ("jedi", "monan_jedi_workflow.jedi_stage", "submit_jedi"),
    ("mpas", "monan_jedi_workflow.mpas_stage", "submit_mpas"),
    ("mpas_init", "monan_jedi_workflow.init_stage", "submit_mpas_init"),
])
def test_login_stage_submits_own_native_pbs(monkeypatch, tmp_path, key, module_name, submit_name):
    import importlib
    module = importlib.import_module(module_name)
    calls = []
    monkeypatch.delenv("PBS_JOBID", raising=False)
    monkeypatch.setattr(platform_backend, "render_run", lambda *args: object())
    monkeypatch.setattr(
        module, submit_name,
        lambda folder, cycle, *, wait: calls.append((folder, cycle, wait)) or "123.pbs",
    )
    op = SimpleNamespace(key=key, site={"execution": {"mode": "pbs"}})
    request = SimpleNamespace(cycle="2025-09-01T00:00:00Z")
    assert platform_backend.execute_native(op, request, tmp_path) == "123.pbs"
    assert calls == [(tmp_path, request.cycle, True)]


def test_no_nested_pbs_submission_from_python_stage(monkeypatch, tmp_path):
    monkeypatch.setenv("PBS_JOBID", "existing.pbs")
    monkeypatch.setattr(platform_backend, "render_run", lambda *args: object())
    op = SimpleNamespace(key="jedi", site={"execution": {"mode": "pbs"}})
    with pytest.raises(RuntimeError, match="login node"):
        platform_backend.execute_native(op, SimpleNamespace(cycle="2025-09-01T00:00:00Z"), tmp_path)


def test_native_pbs_submits_no_python_in_compute_script(monkeypatch, tmp_path):
    import monan_jedi_workflow.native_pbs as helper
    monkeypatch.delenv("PBS_JOBID", raising=False)
    calls = []
    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "qsub":
            return subprocess.CompletedProcess(argv, 0, "825225.pbs-ha\n", "")
        if argv[0] == "qstat":
            return subprocess.CompletedProcess(
                argv, 0,
                "Job Id: 825225.pbs-ha\n    job_state = F\n    Exit_status = 0\n", "",
            )
        raise AssertionError(f"Unexpected scheduler argv: {argv}")
    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    job_id, code = native_pbs_run(
        name="test_ungrib", commands=[["./ungrib.exe"]],
        cwd=tmp_path, stdout=tmp_path / "stdout.log",
        stderr=tmp_path / "stderr.log",
        resources={"queue": "pesqmini", "walltime": "00:10:00",
                   "select": 1, "ncpus": 1, "mpiprocs": 1},
    )
    assert job_id == "825225.pbs-ha" and code == 0
    content = (tmp_path / "test_ungrib.native.pbs").read_text()
    assert "./ungrib.exe" in content
    assert "python" not in content.lower()
    assert "#PBS -V" in content
    assert calls[0][0] == "qsub"


def test_native_pbs_refuses_nested_scheduler(monkeypatch, tmp_path):
    monkeypatch.setenv("PBS_JOBID", "1234.pbs")
    with pytest.raises(RuntimeError, match="login"):
        native_pbs_run(name="x", commands=[["/bin/true"]], cwd=tmp_path,
                       stdout=tmp_path / "out", stderr=tmp_path / "err",
                       resources={"queue": "pesqmini", "walltime": "00:10:00"})
