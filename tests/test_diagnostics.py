"""Self-service diagnosis must identify actionable causes without changing jobs."""
from pathlib import Path
import json
import subprocess

from monan_jedi_workflow.diagnostics import diagnose, main


def _failed_mpas_init(tmp_path):
    root = tmp_path / "example"
    run = root / "work" / "mpas-init" / "20250831T180000Z"
    meta = run / ".monan-jedi-workflow"
    meta.mkdir(parents=True)
    (run / "stderr.log").write_text(
        "./mpas_init_atmosphere: error while loading shared libraries: "
        "libfabric.so.1: cannot open shared object file: No such file or directory\n"
        * 128
    )
    (meta / "mpas-init-validation.json").write_text(json.dumps({
        "job_id": "826106.pbs-ha", "valid": False,
        "missing_outputs": [str(run / "x1.10242.init.2025-08-31_18.00.00.nc")],
        "missing_log_markers": ["Finished running the init_atmosphere core"],
    }))
    state = root / ".platform" / "20250831T180000Z" / "mpas-init" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({
        "state": "invalid", "run_dir": str(run), "attempts": [],
    }))
    return root


def test_diagnose_missing_libfabric_groups_128_rank_errors(tmp_path, monkeypatch):
    root = _failed_mpas_init(tmp_path)
    def fake_run(argv, **kwargs):
        assert argv == ["qstat", "-x", "-f", "826106.pbs-ha"]
        return subprocess.CompletedProcess(
            argv, 0, "Job Id: 826106.pbs-ha\n"
            "    job_state = F\n    Exit_status = 127\n"
            "    resources_used.mem = 0kb\n", "",
        )
    monkeypatch.setattr("monan_jedi_workflow.diagnostics.subprocess.run", fake_run)
    report = diagnose(root)
    assert report["status"] == "failure"
    assert report["diagnosis"]["code"] == "missing-shared-library"
    assert "libfabric.so.1" in report["diagnosis"]["summary"]
    assert report["pbs_jobs"][0]["exit_status"] == 127
    assert len(report["log_evidence"]) == 1
    assert report["log_evidence"][0]["occurrences"] == 128


def test_diagnose_does_not_require_scheduler(tmp_path, monkeypatch):
    root = _failed_mpas_init(tmp_path)
    def forbid(*args, **kwargs):
        raise AssertionError("qstat should not run when --no-pbs")
    monkeypatch.setattr("monan_jedi_workflow.diagnostics.subprocess.run", forbid)
    report = diagnose(root, query_pbs=False)
    assert report["diagnosis"]["code"] == "missing-shared-library"


def test_diagnose_command_returns_human_summary_and_json(tmp_path, capsys):
    root = _failed_mpas_init(tmp_path)
    assert main([str(root), "--no-pbs"]) == 0
    out = capsys.readouterr().out
    assert "libfabric.so.1" in out
    assert "AÇÃO RECOMENDADA" in out
    assert "128 ocorrências da mesma mensagem MPI" in out
    assert main([str(root), "--no-pbs", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failure"


def test_no_failure_is_not_invented(tmp_path):
    root = tmp_path / "empty-case"
    root.mkdir()
    report = diagnose(root, query_pbs=False)
    assert report["status"] == "no-failure-found"
    assert report["diagnosis"]["code"] == "unknown"


def test_diagnose_verbose_preserves_full_pbs_evidence(tmp_path, capsys, monkeypatch):
    root = _failed_mpas_init(tmp_path)
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, 0,
            "Job Id: 826106.pbs-ha\n"
            "    job_state = F\n    Exit_status = 127\n"
            "    Output_Path = host:/p/outputs\n", "",
        )
    monkeypatch.setattr("monan_jedi_workflow.diagnostics.subprocess.run", fake_run)
    assert main([str(root), "--verbose"]) == 0
    out = capsys.readouterr().out
    assert "DETALHES TÉCNICOS" in out
    assert "826106.pbs-ha" in out
    assert "Exit_status=127" in out
    assert "libfabric.so.1" in out


def test_diagnose_detects_present_libfabric_but_missing_pbs_setup(tmp_path, monkeypatch):
    root = _failed_mpas_init(tmp_path)
    run = root / "work" / "mpas-init" / "20250831T180000Z"
    (run / "run_mpas_init.pbs").write_text(
        "#!/bin/bash\n#PBS -V\nmpiexec -n 128 ./mpas_init_atmosphere\n"
    )
    lib_dir = tmp_path / "cray" / "lib64"
    lib_dir.mkdir(parents=True)
    (lib_dir / "libfabric.so.1").write_bytes(b"test fixture")
    monkeypatch.setenv("MONAN_LIBFABRIC_ROOT", str(lib_dir))
    report = diagnose(root, query_pbs=False)
    assert report["runtime_check"]["library_found_on_login"] is True
    assert report["runtime_check"]["scripts_missing_runtime_bootstrap"]
    assert "script PBS não inclui" in report["diagnosis"]["suggestion"]


def test_diagnose_finished_obs_validation_not_false_libfabric(tmp_path):
    root = tmp_path / "case"
    state = root / ".platform" / "20250901T000000Z" / "obs-convert" / "state.json"
    state.parent.mkdir(parents=True)
    work = root / "work" / "obs" / "2025090100"
    logs = work / "logs"
    logs.mkdir(parents=True)
    state.write_text(json.dumps({
        "state": "finished", "run_dir": str(work), "attempts": [],
    }))
    (logs / "run-linker-1.stdout.log").write_text(
        "libfabric.so.1 => /opt/cray/libfabric/1.22.0/lib64/libfabric.so.1 (0x0)\n"
    )
    (root / "work" / "mpas-init" / "20250831T180000Z").mkdir(parents=True)
    (root / "work" / "mpas-init" / "20250831T180000Z" / "stderr.log").write_text(
        "Warning: SEAICE_FRACTIONAL file not found...\n"
    )
    result = diagnose(root, query_pbs=False)
    assert result["status"] == "incomplete"
    assert result["diagnosis"]["code"] == "pending-validation"
    assert result["log_evidence"] == []
    assert result["operations"][0]["operation"] == "obs-convert"



def test_public_dotted_obs_task_filter_finds_hyphenated_runtime_failure(tmp_path):
    root = tmp_path / "case"
    run = root / "work" / "obs" / "2026013000"
    run.mkdir(parents=True)
    state = root / ".platform" / "20260130T000000Z" / "obs-convert" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({
        "state": "invalid",
        "run_dir": str(run),
        "validation_error": "invalid IODA header",
        "attempts": [],
    }))
    report = diagnose(root, task="obs.convert", query_pbs=False)
    assert report["status"] == "failure"
    assert len(report["operations"]) == 1
    assert report["operations"][0]["operation"] == "obs-convert"
    assert "invalid IODA header" in report["operations"][0]["last_error"]


def test_public_dotted_obs_task_filter_preserves_pending_validation(tmp_path):
    root = tmp_path / "case"
    state = root / ".platform" / "20260130T000000Z" / "obs-convert" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"state": "finished", "attempts": []}))
    report = diagnose(root, task="obs.convert", query_pbs=False)
    assert report["status"] == "incomplete"
    assert report["operations"][0]["operation"] == "obs-convert"
