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


def test_external_resolution_and_three_hour_contract(tmp_path, monkeypatch):
    """A fully specified scientific profile may change both mesh and cadence."""
    import shutil
    import monan_jedi_workflow.experiment_start as module
    from monan_jedi_workflow.recipe_config import select_science

    source, bundled = load_recipe("mpas-jedi-3dvar")
    recipe_dir = tmp_path / "recipes" / "custom"
    base = recipe_dir / "science"
    custom = recipe_dir / "profiles" / "60km" / "science"
    shutil.copytree(source, base)
    shutil.copytree(source, custom)
    (recipe_dir / "README.md").write_text("# Custom scientific recipe\n")
    desc = dict(bundled)
    desc["science_source"] = "science"
    desc["resolution_profiles"] = {
        "240km": bundled["resolution_profiles"]["240km"],
        "60km": {
            "mesh": "/shared/mesh-60km",
            "bmatrix": "/shared/B-60km",
            "mesh_id": "x1.40962",
            "levels": 55,
            "cycle": "PT3H",
            "duration": "P1D",
            "background_offset_hours": 1,
            "observations": ["conv", "gpsro"],
            "science_source": "profiles/60km/science",
        },
    }
    (recipe_dir / "recipe.yaml").write_text(yaml.safe_dump(desc))
    for name in ("mpas.yaml", "initialization/mpas.yaml"):
        path = custom / name
        doc = yaml.safe_load(path.read_text())
        mpas = doc["mpas"]
        mpas["lead_hours"] = 3
        mpas["forecast_contract"]["run_hours"] = 3
        mpas["forecast_contract"]["da_state_interval_hours"] = 1
        path.write_text(yaml.safe_dump(doc, sort_keys=False))
    path = custom / "jedi.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["jedi"]["cycle"].update(step_hours=3, window_hours=3, background_offset_hours=-1)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))

    base_science, loaded = load_recipe(recipe_dir)
    settings = resolve_settings(loaded, overrides={"resolution": "60km"})
    assert settings["cycle"] == "PT3H"
    assert settings["duration"] == "P1D"
    selected = select_science(recipe_dir, settings, base_science)
    assert selected == custom
    monkeypatch.setattr(module, "load_project_site", lambda *args, **kwargs: (None, {}))
    monkeypatch.setattr(module, "render_environment", lambda *args, **kwargs: "#!/bin/sh\n")
    case = tmp_path / "case"
    create_experiment(case, start="2026-01-30T03:00:00Z",
                      recipe_source=selected, settings=settings)
    campaign = yaml.safe_load((case / "campaign.yaml").read_text())
    assert campaign["calendar"]["interval"] == "PT3H"
    assert campaign["calendar"]["end"] == "2026-01-31T03:00:00Z"
    assert len(list((case / "work/background").glob("*"))) == 9
    trajectory = (case / "work/background/20260130T030000Z/trajectory.nc")
    assert trajectory.is_symlink()
    assert "2026-01-30_02.00.00.nc" in str(trajectory.readlink())
