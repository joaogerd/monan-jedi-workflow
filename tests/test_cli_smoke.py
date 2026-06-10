import sys
from pathlib import Path

from monan_jedi_workflow import cli


EXPERIMENT_DIR = (
    Path(__file__).resolve().parents[1]
    / "configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"
)
EXPERIMENT_NAME = "3dfgat_mpastatic_x1.10242_2018041500"


def run_cli(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["monan-jedi-workflow", *args])
    return cli.main()


def test_validate_config_cli_reports_baseline_contract(monkeypatch, capsys):
    status = run_cli(monkeypatch, "validate-config", str(EXPERIMENT_DIR))

    captured = capsys.readouterr()

    assert status == 0
    assert "[OK] configuration contract: OK" in captured.out


def test_render_yaml_cli_writes_expected_file(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    status = run_cli(monkeypatch, "render-yaml", str(EXPERIMENT_DIR))

    captured = capsys.readouterr()
    rendered = tmp_path / "build/rendered" / f"{EXPERIMENT_NAME}.yaml"

    assert status == 0
    assert rendered.exists()
    assert "[OK] rendered YAML:" in captured.out
    assert "cost function:" in rendered.read_text()


def test_render_pbs_cli_writes_executable_script(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    status = run_cli(monkeypatch, "render-pbs", str(EXPERIMENT_DIR))

    captured = capsys.readouterr()
    rendered = tmp_path / "build/rendered" / f"{EXPERIMENT_NAME}.pbs"

    assert status == 0
    assert rendered.exists()
    assert rendered.stat().st_mode & 0o111
    assert "[OK] rendered PBS:" in captured.out
    assert "mpasjedi_variational.x" in rendered.read_text()


def test_render_pbs_cli_avoids_legacy_workflow_environment_source(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)

    status = run_cli(monkeypatch, "render-pbs", str(EXPERIMENT_DIR))

    capsys.readouterr()
    rendered = tmp_path / "build/rendered" / f"{EXPERIMENT_NAME}.pbs"
    content = rendered.read_text()

    assert status == 0
    assert "source /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow" not in content
    assert "export MONAN_JEDI_INSTALL_BIN_DIR=" in content
    assert "export JEDI_EXECUTABLE=" in content


def test_render_pbs_cli_detects_mpi_layout_from_pbs_nodefile(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)

    status = run_cli(monkeypatch, "render-pbs", str(EXPERIMENT_DIR))

    capsys.readouterr()
    rendered = tmp_path / "build/rendered" / f"{EXPERIMENT_NAME}.pbs"
    content = rendered.read_text()

    assert status == 0
    assert "PBS_NODEFILE" in content
    assert "NP=$(wc -l <" in content
    assert "NNODES=$(sort -u" in content
    assert "mpiexec -n \"${NP}\"" in content
    assert "run_3dfgat_workflow_geometry_background_np${NP}.${PBS_JOBID}.log" in content
