"""Regression: native stages must render the same stack setup as main.

The test isolates the profile interface; full Cray module initialization is
verified against the actual installation manifest on JACI.
"""
from pathlib import Path
import yaml
import pytest

from monan_jedi_workflow.scientific_environment import render_native_site_setup
from monan_jedi_workflow.experiment_start import create_experiment


def test_site_environment_is_rendered_by_shared_main_utility(tmp_path, monkeypatch):
    site = tmp_path / "site.yaml"
    site.write_text("site:\n  name: test\n")
    seen = []
    def fake_render(path):
        seen.append(Path(path))
        return "module purge\nmodule load test\nexport LD_LIBRARY_PATH=/example/lib\n"
    monkeypatch.setattr(
        "monan_jedi_workflow.scientific_environment.render_site_environment_block",
        fake_render,
    )
    output = render_native_site_setup({"site_config": "site.yaml"}, config_dir=tmp_path)
    assert seen == [site.resolve()]
    assert output == [
        "module purge",
        "module load test",
        "export LD_LIBRARY_PATH=/example/lib",
    ]


def test_missing_site_configuration_fails_before_pbs_submission(tmp_path):
    with pytest.raises(FileNotFoundError, match="site profile not found"):
        render_native_site_setup(
            {"site_config": str(tmp_path / "missing.yaml")}, config_dir=tmp_path
        )


def test_legacy_unconfigured_stage_does_not_force_site_profile(tmp_path):
    assert render_native_site_setup({}, config_dir=tmp_path) == []


def test_new_first_experiment_all_native_stages_reference_shared_site(tmp_path):
    root = tmp_path / "case"
    create_experiment(root)
    site = root / "science/site.yaml"
    profile = yaml.safe_load(site.read_text())
    assert profile["stack"]["load"] is True
    assert profile["runtime"]["validate_python"] is False
    assert profile["stack"]["root"] == "${STACK_ROOT}"
    for rel, key in (
        ("science/jedi.yaml", "jedi"),
        ("science/mpas.yaml", "mpas"),
        ("science/initialization/mpas.yaml", "mpas"),
        ("science/initialization/mpas_init.yaml", "mpas_init"),
        ("science/initialization/wps.yaml", "wps"),
        ("science/obs2ioda.yaml", "obs2ioda"),
    ):
        data = yaml.safe_load((root / rel).read_text())
        assert data[key]["pbs"]["site_config"] == str(site)


@pytest.mark.parametrize("stage_module", [
    "monan_jedi_workflow.mpas_stage",
    "monan_jedi_workflow.jedi_stage",
])
def test_native_mpi_pbs_sources_site_before_launcher(tmp_path, monkeypatch, stage_module):
    import importlib
    from types import SimpleNamespace
    module = importlib.import_module(stage_module)
    monkeypatch.setattr(
        module, "render_native_site_setup",
        lambda pbs, *, config_dir: [
            "module purge",
            "module load installed-scientific-stack",
            "export LD_LIBRARY_PATH=/scientific/stack/lib",
        ],
    )
    run = SimpleNamespace(
        config={
            "pbs": {
                "queue": "pesqmini",
                "select": 1, "ncpus": 1, "mpiprocs": 1,
                "walltime": "00:10:00",
                "launcher": "mpiexec",
                "command": ["./mpas_init_atmosphere"],
                "site_config": str(tmp_path / "site.yaml"),
            },
        },
        context={},
        config_dir=tmp_path,
        run_dir=tmp_path,
        pbs_path=tmp_path / "science.pbs",
    )
    module._render_pbs(run)
    content = run.pbs_path.read_text()
    assert content.index("module purge") < content.index("module load installed-scientific-stack")
    assert content.index("module load installed-scientific-stack") < content.index(
        "mpiexec -n 1 ./mpas_init_atmosphere"
    )
    assert "export LD_LIBRARY_PATH=/scientific/stack/lib" in content
    assert "python" not in content.lower()


def test_real_main_site_renderer_loads_stack_before_native_jobs(tmp_path, monkeypatch):
    import json
    install = tmp_path / "installed-monan-jedi"
    manifest = install / "share" / "monan-jedi" / "install-manifest.json"
    manifest.parent.mkdir(parents=True)
    stack = tmp_path / "stack"
    module_dir = stack / "envs" / "monan-jedi-env" / "modules"
    module_dir.mkdir(parents=True)
    (stack / "site").mkdir(parents=True)
    (stack / "site" / "setup.sh").write_text("# site\n")
    manifest.write_text(json.dumps({
        "schema_version": 2,
        "ecosystem_contract_version": 2,
        "contract": "monan-jedi-runtime-v2",
        "public_anchors": ["MONAN_JEDI_INSTALL_ROOT", "STACK_ROOT"],
        "stack": {
            "env_name": "monan-jedi-env",
            "env_module": "monan-jedi-env",
            "site_setup": "site/setup.sh",
            "module_root_template": "envs/{env_name}/modules",
        },
    }))
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", str(install))
    monkeypatch.setenv("STACK_ROOT", str(stack))
    site = tmp_path / "site.yaml"
    site.write_text(
        "site:\n  name: jaci\n"
        "stack:\n  load: true\n  root: ${STACK_ROOT}\n"
        "jedi:\n  install_root: ${MONAN_JEDI_INSTALL_ROOT}\n"
        "runtime:\n  validate_python: false\n"
    )
    code = "\n".join(render_native_site_setup(
        {"site_config": str(site)}, config_dir=tmp_path
    ))
    assert "module purge" in code
    assert 'source "${STACK_SITE_SETUP}"' in code
    assert 'module use "${STACK_MODULE_ROOT}"' in code
    assert 'module load "${STACK_ENV_MODULE}"' in code
    assert "LD_LIBRARY_PATH" in code
    assert "python3 -" not in code


def test_wps_and_obs_native_pbs_use_same_site_bootstrap(tmp_path, monkeypatch):
    import subprocess
    import monan_jedi_workflow.native_pbs as native
    monkeypatch.delenv("PBS_JOBID", raising=False)
    monkeypatch.setattr(
        native, "render_native_site_setup",
        lambda resources, *, config_dir: ["module purge", "module load scientific-env"],
    )
    def fake_run(argv, **kwargs):
        if argv[0] == "qsub":
            return subprocess.CompletedProcess(argv, 0, "1000.pbs-ha\n", "")
        return subprocess.CompletedProcess(
            argv, 0,
            "job_state = F\nExit_status = 0\n", ""
        )
    monkeypatch.setattr(native.subprocess, "run", fake_run)
    native.native_pbs_run(
        name="test_converter", commands=[["./obs2ioda"]],
        cwd=tmp_path, stdout=tmp_path / "out.log", stderr=tmp_path / "err.log",
        resources={"queue": "pesqmini", "select": 1, "ncpus": 1,
                   "mpiprocs": 1, "walltime": "00:10:00",
                   "site_config": str(tmp_path / "site.yaml")},
    )
    script = (tmp_path / "test_converter.native.pbs").read_text()
    assert "module load scientific-env" in script
    assert script.index("module load scientific-env") < script.index("./obs2ioda")
    assert "python" not in script.lower()
