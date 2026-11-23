"""Regression tests for recipe-first creation; no HPC jobs or scientific data."""
from pathlib import Path
import pytest
import yaml

from monan_jedi_workflow.recipe_config import load_recipe, resolve_settings
from monan_jedi_workflow.experiment_start import _duration, create_experiment


def test_builtin_recipe_has_documented_defaults():
    science, desc = load_recipe("mpas-jedi-3dvar")
    assert (science / "jedi.yaml").is_file()
    assert desc["defaults"]["resolution"] == "240km"
    settings = resolve_settings(desc)
    assert settings["duration"] == "PT6H"
    assert settings["observations"] == ["conv", "gpsro"]


def test_user_yaml_and_cli_precedence(tmp_path):
    _, desc = load_recipe("mpas-jedi-3dvar")
    config = tmp_path / "config.yaml"
    config.write_text("duration: P3D\n")
    settings = resolve_settings(desc, config=config, overrides={"duration": "P7D"})
    assert settings["duration"] == "P7D"
    assert settings["resolution"] == "240km"


@pytest.mark.parametrize("overrides", [
    {"resolution": "60km"}, {"levels": 72}, {"cycle": "PT3H"},
    {"mode": "warm"}, {"observations": ["conv"]},
    {"bmatrix": "/invalid/b.nc"}, {"timestep": 100},
])
def test_unsupported_science_changes_fail_closed(overrides):
    _, desc = load_recipe("mpas-jedi-3dvar")
    with pytest.raises(ValueError):
        resolve_settings(desc, overrides=overrides)


def test_duration():
    assert _duration("P7D").total_seconds() == 7 * 86400
    assert _duration("PT6H").total_seconds() == 21600
    with pytest.raises(ValueError):
        _duration("PT5H")


@pytest.mark.parametrize("duration,expected", [("PT6H", 2), ("P3D", 13), ("P7D", 29)])
def test_materialization_all_background_links(tmp_path, monkeypatch, duration, expected):
    import monan_jedi_workflow.experiment_start as module

    monkeypatch.setattr(
        module, "load_project_site",
        lambda *args, **kwargs: (None, {}),
    )
    monkeypatch.setattr(
        module, "render_environment",
        lambda *args, **kwargs: "#!/bin/sh\n",
    )
    science, desc = load_recipe("mpas-jedi-3dvar")
    settings = resolve_settings(desc, overrides={"duration": duration})
    case = tmp_path / "case"
    create_experiment(case, start="2026-01-30T00:00:00Z",
                      recipe_source=science, settings=settings)
    campaign = yaml.safe_load((case / "campaign.yaml").read_text())
    assert campaign["calendar"]["end_inclusive"] is True
    assert campaign["calendar"]["interval"] == "PT6H"
    backgrounds = list((case / "work/background").glob("*"))
    assert len(backgrounds) == expected
    assert all((folder / "state.nc").is_symlink() for folder in backgrounds)
    assert all((folder / "trajectory.nc").is_symlink() for folder in backgrounds)
    assert (case / "recipe-lock.json").is_file()
