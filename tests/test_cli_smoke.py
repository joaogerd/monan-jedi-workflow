import json
import sys
from pathlib import Path

from monan_jedi_workflow import cli


EXPERIMENT_DIR = (
    Path(__file__).resolve().parents[1]
    / "configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"
)
EXPERIMENT_NAME = "3dfgat_mpastatic_x1.10242_2018041500"


def _write_runtime_contract(install_root: Path) -> None:
    manifest = install_root / "share" / "monan-jedi" / "install-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "ecosystem_contract_version": 2,
                "contract": "monan-jedi-runtime-v2",
                "public_anchors": ["MONAN_JEDI_INSTALL_ROOT", "STACK_ROOT"],
                "stack": {
                    "env_name": "jaci-test",
                    "env_module": "test/jedi-mpas-env/2.0.0",
                    "site_setup": "configs/sites/tier2/jaci/setup.sh",
                    "module_root_template": "envs/{env_name}/modules",
                },
            }
        ),
        encoding="utf-8",
    )


def run_cli(monkeypatch, tmp_path: Path, *args: str) -> int:
    install = tmp_path / "monan-jedi"
    _write_runtime_contract(install)
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", str(install))
    monkeypatch.setenv("STACK_ROOT", str(tmp_path / "spack-stack"))
    monkeypatch.setattr(sys, "argv", ["monan-jedi-workflow", *args])
    return cli.main()


def test_validate_config_cli_reports_baseline_contract(monkeypatch, tmp_path, capsys):
    status = run_cli(monkeypatch, tmp_path, "validate-config", str(EXPERIMENT_DIR))

    captured = capsys.readouterr()

    assert status == 0
    assert "[OK] configuration contract: OK" in captured.out


def test_render_yaml_cli_writes_expected_file(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    status = run_cli(monkeypatch, tmp_path, "render-yaml", str(EXPERIMENT_DIR))

    captured = capsys.readouterr()
    rendered = tmp_path / "build/rendered" / f"{EXPERIMENT_NAME}.yaml"

    assert status == 0
    assert rendered.exists()
    assert "[OK] rendered YAML:" in captured.out
    assert "cost function:" in rendered.read_text()


def test_render_pbs_cli_writes_executable_script(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    status = run_cli(monkeypatch, tmp_path, "render-pbs", str(EXPERIMENT_DIR))

    captured = capsys.readouterr()
    rendered = tmp_path / "build/rendered" / f"{EXPERIMENT_NAME}.pbs"

    assert status == 0
    assert rendered.exists()
    assert rendered.stat().st_mode & 0o111
    assert "[OK] rendered PBS:" in captured.out
    content = rendered.read_text()
    assert "mpasjedi_variational.x" in content
    assert content.count("#PBS -l place=excl") == 1


def test_render_pbs_cli_avoids_legacy_workflow_environment_source(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)

    status = run_cli(monkeypatch, tmp_path, "render-pbs", str(EXPERIMENT_DIR))

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

    status = run_cli(monkeypatch, tmp_path, "render-pbs", str(EXPERIMENT_DIR))

    capsys.readouterr()
    rendered = tmp_path / "build/rendered" / f"{EXPERIMENT_NAME}.pbs"
    content = rendered.read_text()

    assert status == 0
    assert "PBS_NODEFILE" in content
    assert "NP=$(wc -l <" in content
    assert "NNODES=$(sort -u" in content
    assert "mpiexec -n \"${NP}\"" in content
    assert "run_3dfgat_workflow_geometry_background_np${NP}.${PBS_JOBID}.log" in content
