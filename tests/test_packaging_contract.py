"""A clean pip install must include the orchestration executable dependency."""
from pathlib import Path


def test_core_install_declares_verified_simpleworkflow_source():
    metadata = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    dependencies = metadata.split("[project.optional-dependencies]", 1)[0]
    assert (
        "simpleworkflow @ git+https://github.com/joaogerd/simpleWorkflow.git@"
        "b38733cb77950810a510d22cd96a999b53150f95"
    ) in dependencies


def test_normal_install_still_exports_all_seven_user_commands():
    metadata = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    scripts = metadata.split("[project.scripts]", 1)[1].split("\n[", 1)[0]
    for command in (
        "experiment", "wps", "obs", "mpas", "jedi", "diagnostic", "diagnose"
    ):
        assert f"{command} = " in scripts
