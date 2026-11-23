"""Recipe discovery and explicit user overrides for experiment creation.

A recipe supplies the scientific defaults. Only non-None CLI options override it.
Scientific resources are never guessed from a nominal resolution.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import yaml

BUILTIN = "mpas-jedi-3dvar"


def _read(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Recipe/config must be a mapping: {path}")
    return data


def recipe_directory(recipe: str | Path) -> Path:
    value = str(recipe)
    if value == BUILTIN:
        return (Path(__file__).resolve().parent / "recipes" / BUILTIN)
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
    if not isinstance(source, str) or not source:
        raise ValueError("recipe science_source must name a directory")
    science = (directory / source).resolve()
    if not science.is_relative_to(directory.resolve()):
        raise ValueError("science_source must remain within the selected recipe")
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
    supplied = set(user) | set(explicit)
    for key in ("levels", "cycle", "duration", "observations", "timestep"):
        if key not in supplied and key in profile:
            settings[key] = deepcopy(profile[key])
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
        raise ValueError("Warm start científico não implementado; requer restart validado")
    if not isinstance(settings.get("observations"), list) or not settings["observations"]:
        raise ValueError("observations must be a nonempty list")
    supported = set(recipe.get("available_observations", ["conv", "gpsro"]))
    if not set(settings["observations"]).issubset(supported):
        raise ValueError("Selected observations are not declared by the recipe; "
                         "a compatible converter and UFO configuration is required")
    # Strict contract: do not silently reinterpret the tested 240 km science
    # files as another mesh or change its numerical/observation assumptions.
    if res != "240km":
        # New scientific resolutions are supported through a complete
        # per-resolution science directory; nominal resolution alone is unsafe.
        if not profile.get("science_source") or not profile.get("mesh_id"):
            raise ValueError(
                f"Resolution {res} needs a complete science_source and mesh_id "
                "in its recipe resolution profile; refusing 240 km reuse"
            )
    if settings.get("levels") != profile.get("levels", 55):
        raise ValueError("Requested levels require a matching profile with compatible science templates")
    if settings.get("cycle") != profile.get("cycle", "PT6H"):
        raise ValueError("Requested cycle requires a matching scientific profile and MPAS/JEDI timing contract")
    offset = profile.get("background_offset_hours", 3)
    interval_hours = int(settings["cycle"][2:-1])
    if not isinstance(offset, int) or not (0 < offset < interval_hours):
        raise ValueError("background_offset_hours must be an integer strictly inside the cycle")
    if set(settings["observations"]) != set(profile.get("observations", ["conv", "gpsro"])):
        raise ValueError("Requested observations require matching converter/UFO templates in the profile")
    if settings.get("mesh") != profile["mesh"]:
        raise ValueError("Custom mesh requires a matching resolution profile and MPAS/JEDI templates")
    # The covariance directory is a JEDI runtime input; users may select a
    # different B for the SAME mesh/level contract. Its existence/contents are
    # checked during preflight and scientific validation, not inferred here.
    if not isinstance(settings.get("bmatrix"), str) or not settings["bmatrix"].strip():
        raise ValueError("bmatrix must be a nonempty covariance directory path")
    if settings.get("timestep") is not None and settings["timestep"] != profile.get("timestep"):
        raise ValueError("Model timestep override requires a matching profile/namelist")
    return settings


def select_science(recipe: str | Path, settings: dict, base: Path) -> Path:
    """Use complete per-resolution science assets, never partial 240 km overlays."""
    profile = settings["profile"]
    source = profile.get("science_source")
    if not source:
        return base
    directory = recipe_directory(recipe)
    root = (directory / source).resolve()
    if not root.is_relative_to(directory.resolve()) or not root.is_dir():
        raise ValueError(f"Invalid resolution science_source: {source!r}")
    required = ("jedi.yaml", "mpas.yaml", "obs2ioda.yaml",
                "initialization/mpas.yaml", "initialization/mpas_init.yaml",
                "initialization/wps.yaml")
    for name in required:
        if not (root / name).is_file():
            raise ValueError(f"Resolution science profile missing {name}: {root}")
    return root
