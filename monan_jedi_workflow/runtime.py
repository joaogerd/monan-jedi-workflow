"""Runtime preparation for the minimal MONAN-JEDI baseline workflow."""

from __future__ import annotations

from pathlib import Path

from .config import ExperimentConfig, require_key


# MPAS physics and lookup files required by namelist.atmosphere_240km.
# These files were present in the validated manual baseline execution directory
# and are needed by mpas_init/core_physics, for example OZONE_PLEV.TBL.
DEFAULT_MPAS_PHYSICS_FILES = [
    "CAM_ABS_DATA.DBL",
    "CAM_AEROPT_DATA.DBL",
    "COMPATIBILITY",
    "GENPARM.TBL",
    "LANDUSE.TBL",
    "OZONE_DAT.TBL",
    "OZONE_LAT.TBL",
    "OZONE_PLEV.TBL",
    "RRTMG_LW_DATA",
    "RRTMG_LW_DATA.DBL",
    "RRTMG_SW_DATA",
    "RRTMG_SW_DATA.DBL",
    "SOILPARM.TBL",
    "VEGPARM.TBL",
]


def get_work_root(config: ExperimentConfig) -> Path:
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    return Path(str(require_key(paths, "work_root", "experiment.yaml paths")))


def get_data_root(config: ExperimentConfig) -> Path:
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    return Path(str(require_key(paths, "data_root", "experiment.yaml paths")))


def get_runtime_dir(config: ExperimentConfig) -> Path:
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    runtime_dir = Path(str(require_key(paths, "runtime_dir", "experiment.yaml paths")))
    if runtime_dir.is_absolute():
        return runtime_dir
    return get_work_root(config) / runtime_dir


def get_rendered_dir(config: ExperimentConfig) -> Path:
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    rendered_dir = Path(str(require_key(paths, "rendered_dir", "experiment.yaml paths")))
    if rendered_dir.is_absolute():
        return rendered_dir
    return get_work_root(config) / rendered_dir


def _resolve_source(source: str, data_root: Path) -> Path:
    path = Path(str(source))
    if path.is_absolute():
        return path
    return data_root / path


def _resolve_target(target: str, runtime_dir: Path) -> Path:
    path = Path(str(target))
    if path.is_absolute():
        return path
    return runtime_dir / path


def _link_or_keep(source: Path, target: Path) -> str:
    if not source.exists():
        raise FileNotFoundError(f"Missing runtime source: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            current = target.resolve()
            desired = source.resolve()
            if current == desired:
                return f"[OK] link exists: {target} -> {current}"
            target.unlink()
            target.symlink_to(source)
            return f"[INFO] updated link: {target} -> {source}"

        raise FileExistsError(
            f"Runtime target exists and is not a symlink; refusing to overwrite: {target}"
        )

    target.symlink_to(source)
    return f"[OK] linked: {target} -> {source}"


def _physics_file_links(runtime_cfg: dict, data_root: Path) -> list[tuple[Path, str]]:
    """Return MPAS physics file links to stage in the execution directory."""
    physics_cfg = runtime_cfg.get("physics_files", {})

    if physics_cfg is False:
        return []

    if isinstance(physics_cfg, dict):
        root = Path(str(physics_cfg.get("root", data_root / "MPAS_namelist_stream_physics_files")))
        files = physics_cfg.get("files", DEFAULT_MPAS_PHYSICS_FILES)
    else:
        root = data_root / "MPAS_namelist_stream_physics_files"
        files = DEFAULT_MPAS_PHYSICS_FILES

    return [(root / str(filename), str(filename)) for filename in files]


def prepare_runtime(config: ExperimentConfig) -> list[str]:
    """Create runtime directories and symlinks declared in runtime.yaml."""
    runtime_cfg = require_key(config.runtime, "runtime", "runtime.yaml")
    required_dirs = require_key(runtime_cfg, "required_directories", "runtime.yaml")
    required_links = require_key(runtime_cfg, "required_links", "runtime.yaml")

    data_root = get_data_root(config)
    runtime_dir = get_runtime_dir(config)

    messages: list[str] = []
    runtime_dir.mkdir(parents=True, exist_ok=True)
    messages.append(f"[OK] runtime directory: {runtime_dir}")

    for directory in required_dirs:
        path = runtime_dir / str(directory)
        path.mkdir(parents=True, exist_ok=True)
        messages.append(f"[OK] directory: {path}")

    for item in required_links:
        if not isinstance(item, dict):
            raise TypeError("Each runtime.required_links entry must be a mapping")
        source = _resolve_source(str(require_key(item, "source", "runtime.required_links")), data_root)
        target = _resolve_target(str(require_key(item, "target", "runtime.required_links")), runtime_dir)
        messages.append(_link_or_keep(source, target))

    for source, target_name in _physics_file_links(runtime_cfg, data_root):
        target = runtime_dir / target_name
        messages.append(_link_or_keep(source, target))

    return messages
