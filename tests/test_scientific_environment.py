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
