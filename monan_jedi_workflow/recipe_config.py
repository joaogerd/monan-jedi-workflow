"""Recipe discovery and explicit user overrides for experiment creation.

A recipe supplies the scientific defaults. Only non-None CLI options override it.
Scientific resources are never guessed from a nominal resolution.
"""
from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path
import re
import yaml

BUILTIN = "mpas-jedi-3dvar"
BUNDLED = "reference-20250901"


def _read(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Recipe/config must be a mapping: {path}")
    return data


def recipe_directory(recipe: str | Path) -> Path:
    value = str(recipe)
    if value == BUILTIN:
        return Path(str(files("monan_jedi_workflow").joinpath("recipes", BUILTIN)))
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"Unknown recipe {recipe!r}; use '{BUILTIN}' or an existing directory")
    return path


def load_recipe(recipe: str | Path = BUILTIN) -> tuple[Path, dict]:
    directory = recipe_directory(recipe)
    path = directory / "recipe.yaml"
    if not path.is_file():
        raise ValueError(f"Recipe descriptor is missing: {path}")
    data = _read(path)
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported recipe schema in {path}")
    if not (directory / "README.md").is_file():
        raise ValueError(f"Every recipe must have a README.md: {directory}")
    source = data.get("science_source")
    if source == BUNDLED:
        science = Path(str(files("monan_jedi_workflow").joinpath("catalog", BUNDLED)))
    elif isinstance(source, str) and source:
        science = (directory / source).resolve()
        if not science.is_relative_to(directory.resolve()):
            raise ValueError("science_source must remain within the external recipe")
    else:
        raise ValueError("recipe science_source must name a directory")
    if not science.is_dir():
        raise ValueError(f"Recipe science directory does not exist: {science}")
    return science, data


def resolve_settings(recipe: dict, *, config: Path | None = None, overrides: dict | None = None) -> dict:
    defaults = recipe.get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError("Recipe must define defaults")
    settings = deepcopy(defaults)
    # Named resolution profiles provide a compatible set of scientific assets.
    user = _read(Path(config)) if config is not None else {}
    explicit = {k: v for k, v in (overrides or {}).items() if v is not None}
    unknown = (set(user) | set(explicit)) - set(defaults)
    if unknown:
        raise ValueError(f"Unknown recipe setting(s): {', '.join(sorted(unknown))}")
    settings.update(user)
    settings.update(explicit)
    res = settings.get("resolution")
    profiles = recipe.get("resolution_profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("resolution_profiles must be a mapping")
    if res not in profiles:
        raise ValueError(
            f"No scientific profile for resolution {res!r}. "
            "Add a validated resolution_profiles entry with mesh, covariance and resource paths; "
            "the workflow must not reuse the reference 240 km files."
        )
    profile = profiles[res]
    if not isinstance(profile, dict):
        raise ValueError("Resolution profile must be a mapping")
    for key in ("mesh", "bmatrix"):
        if not profile.get(key) and not settings.get(key):
            raise ValueError(f"Resolution {res}: missing required {key} mapping")
    settings["profile"] = deepcopy(profile)
    for key in ("mesh", "bmatrix", "timestep"):
        if settings.get(key) is None and key in profile:
            settings[key] = profile[key]
    if not re.fullmatch(r"PT[1-9][0-9]*H", str(settings.get("cycle"))):
        raise ValueError("cycle must be an ISO-8601 whole-hour interval such as PT6H")
    if settings.get("mode") != "cold":
        raise ValueError("Scientific warm start is not implemented")
    if not isinstance(settings.get("observations"), list) or not settings["observations"]:
        raise ValueError("observations must be a nonempty list")
    supported = {"conv", "gpsro"}
    if not set(settings["observations"]).issubset(supported):
        raise ValueError("Current Obs2IODA reference supports conv,gpsro only; "
                         "other observation types need a compatible converter/operator recipe")
    return settings
