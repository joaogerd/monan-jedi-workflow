"""Runtime preparation for the minimal MONAN-JEDI baseline workflow.

The runtime layer creates the directory structure and symbolic links required
to execute the validated MPAS-JEDI 3D-FGAT baseline. It deliberately avoids
copying large scientific input files and instead stages them through symlinks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    """Return the configured workflow work root.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    pathlib.Path
        Path stored in ``experiment.yaml`` under ``paths.work_root``.

    Raises
    ------
    KeyError
        If ``paths`` or ``paths.work_root`` is missing.

    Notes
    -----
    The returned path is not resolved or created here. Resolution is deferred
    to callers that need absolute paths, while directory creation is handled by
    runtime preparation routines.

    See Also
    --------
    get_runtime_dir : Resolve the runtime directory relative to the work root.
    get_rendered_dir : Resolve the rendered-file directory relative to the work root.

    Examples
    --------
    >>> from pathlib import Path
    >>> from monan_jedi_workflow.config import ExperimentConfig
    >>> cfg = ExperimentConfig(
    ...     root=Path("."),
    ...     experiment={"paths": {"work_root": "/tmp/work"}},
    ...     runtime={}, variables={}, observations={}, pbs={},
    ... )
    >>> get_work_root(cfg)
    PosixPath('/tmp/work')
    """
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    return Path(str(require_key(paths, "work_root", "experiment.yaml paths")))


def get_data_root(config: ExperimentConfig) -> Path:
    """Return the configured input data root.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    pathlib.Path
        Path stored in ``experiment.yaml`` under ``paths.data_root``.

    Raises
    ------
    KeyError
        If ``paths`` or ``paths.data_root`` is missing.

    Notes
    -----
    Relative runtime sources are resolved against this directory. This keeps
    data staging independent of the current shell working directory.

    See Also
    --------
    _resolve_source : Resolve a configured source path against this root.
    prepare_runtime : Stage links using the returned data root.

    Examples
    --------
    >>> from pathlib import Path
    >>> from monan_jedi_workflow.config import ExperimentConfig
    >>> cfg = ExperimentConfig(
    ...     root=Path("."),
    ...     experiment={"paths": {"data_root": "/data/jedi"}},
    ...     runtime={}, variables={}, observations={}, pbs={},
    ... )
    >>> get_data_root(cfg).name
    'jedi'
    """
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    return Path(str(require_key(paths, "data_root", "experiment.yaml paths")))


def get_runtime_dir(config: ExperimentConfig) -> Path:
    """Return the runtime directory for the experiment.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    pathlib.Path
        Absolute or work-root-relative runtime directory.

    Raises
    ------
    KeyError
        If ``paths.runtime_dir`` or ``paths.work_root`` is missing.

    Notes
    -----
    Absolute ``runtime_dir`` values are respected. Relative values are joined
    with ``work_root`` so the configuration can remain portable across clones
    or HPC project directories.

    See Also
    --------
    get_work_root : Return the base directory for relative runtime paths.
    prepare_runtime : Create the runtime directory and staged inputs.

    Examples
    --------
    >>> from pathlib import Path
    >>> from monan_jedi_workflow.config import ExperimentConfig
    >>> cfg = ExperimentConfig(
    ...     root=Path("."),
    ...     experiment={"paths": {"work_root": "/tmp/work", "runtime_dir": "run"}},
    ...     runtime={}, variables={}, observations={}, pbs={},
    ... )
    >>> get_runtime_dir(cfg)
    PosixPath('/tmp/work/run')
    """
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    runtime_dir = Path(str(require_key(paths, "runtime_dir", "experiment.yaml paths")))

    # Absolute runtime paths are considered authoritative. Relative paths are
    # interpreted relative to work_root for reproducible workflow layouts.
    if runtime_dir.is_absolute():
        return runtime_dir
    return get_work_root(config) / runtime_dir


def get_rendered_dir(config: ExperimentConfig) -> Path:
    """Return the directory where rendered YAML and PBS files are written.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    pathlib.Path
        Absolute or work-root-relative rendered output directory.

    Raises
    ------
    KeyError
        If ``paths.rendered_dir`` or ``paths.work_root`` is missing.

    Notes
    -----
    Keeping rendered files separate from the runtime directory makes it easier
    to compare generated YAML/PBS files without mixing them with execution logs
    and model outputs.

    See Also
    --------
    get_work_root : Return the base directory for relative rendered paths.
    monan_jedi_workflow.render.write_rendered_yaml : Write rendered YAML files.
    monan_jedi_workflow.render.write_rendered_pbs : Write rendered PBS files.

    Examples
    --------
    >>> from pathlib import Path
    >>> from monan_jedi_workflow.config import ExperimentConfig
    >>> cfg = ExperimentConfig(
    ...     root=Path("."),
    ...     experiment={"paths": {"work_root": "/tmp/work", "rendered_dir": "rendered"}},
    ...     runtime={}, variables={}, observations={}, pbs={},
    ... )
    >>> get_rendered_dir(cfg)
    PosixPath('/tmp/work/rendered')
    """
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    rendered_dir = Path(str(require_key(paths, "rendered_dir", "experiment.yaml paths")))
    if rendered_dir.is_absolute():
        return rendered_dir
    return get_work_root(config) / rendered_dir


def _resolve_source(source: str, data_root: Path) -> Path:
    """Resolve a configured runtime source path.

    Parameters
    ----------
    source : str
        Source path from ``runtime.required_links``.
    data_root : pathlib.Path
        Base data directory used for relative source paths.

    Returns
    -------
    pathlib.Path
        Absolute source path, or a path joined with ``data_root`` when the
        configured source is relative.

    Raises
    ------
    None

    Notes
    -----
    Source resolution is intentionally separate from existence checks. This
    allows callers to build precise diagnostic messages at the point where the
    link is staged.

    See Also
    --------
    _resolve_target : Resolve runtime target paths.
    _link_or_keep : Create or update symbolic links.

    Examples
    --------
    >>> _resolve_source("background/file.nc", Path("/data"))
    PosixPath('/data/background/file.nc')
    >>> _resolve_source("/scratch/file.nc", Path("/data"))
    PosixPath('/scratch/file.nc')
    """
    path = Path(str(source))
    if path.is_absolute():
        return path
    return data_root / path


def _resolve_target(target: str, runtime_dir: Path) -> Path:
    """Resolve a configured runtime target path.

    Parameters
    ----------
    target : str
        Target path from ``runtime.required_links``.
    runtime_dir : pathlib.Path
        Runtime directory used for relative target paths.

    Returns
    -------
    pathlib.Path
        Absolute target path, or a path joined with ``runtime_dir`` when the
        configured target is relative.

    Raises
    ------
    None

    Notes
    -----
    Targets are normally relative to the execution directory so the staged
    layout mirrors what MPAS-JEDI expects at runtime.

    See Also
    --------
    _resolve_source : Resolve source paths.
    _link_or_keep : Create or update symbolic links.

    Examples
    --------
    >>> _resolve_target("Data/os/obs.h5", Path("/run"))
    PosixPath('/run/Data/os/obs.h5')
    """
    path = Path(str(target))
    if path.is_absolute():
        return path
    return runtime_dir / path


def _link_or_keep(source: Path, target: Path) -> str:
    """Create a symbolic link or keep an existing valid one.

    Parameters
    ----------
    source : pathlib.Path
        Existing source file or directory that should be linked.
    target : pathlib.Path
        Symbolic link location to create inside the runtime tree.

    Returns
    -------
    str
        Status message describing whether the link was created, already valid,
        or updated.

    Raises
    ------
    FileNotFoundError
        If ``source`` does not exist.
    FileExistsError
        If ``target`` exists and is not a symbolic link.

    Notes
    -----
    This function is idempotent for links that already point to the requested
    source. If a symbolic link exists but points elsewhere, it is replaced.
    Real files or directories are never overwritten, which protects manually
    generated products in shared HPC runtime directories.

    See Also
    --------
    prepare_runtime : Stage all runtime links declared by the configuration.

    Examples
    --------
    >>> callable(_link_or_keep)
    True
    """
    if not source.exists():
        raise FileNotFoundError(f"Missing runtime source: {source}")

    # The target parent may be a nested MPAS-JEDI directory such as Data/os.
    # Creating it here keeps individual link entries concise in runtime.yaml.
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            current = target.resolve()
            desired = source.resolve()
            if current == desired:
                return f"[OK] link exists: {target} -> {current}"

            # A stale symlink is safe to replace because it does not contain
            # data itself. This keeps reruns consistent after data_root changes.
            target.unlink()
            target.symlink_to(source)
            return f"[INFO] updated link: {target} -> {source}"

        raise FileExistsError(
            f"Runtime target exists and is not a symlink; refusing to overwrite: {target}"
        )

    target.symlink_to(source)
    return f"[OK] linked: {target} -> {source}"


def _physics_file_links(runtime_cfg: dict[str, Any], data_root: Path) -> list[tuple[Path, str]]:
    """Return MPAS physics file links to stage in the execution directory.

    Parameters
    ----------
    runtime_cfg : dict[str, typing.Any]
        Runtime configuration mapping loaded from ``runtime.yaml``.
    data_root : pathlib.Path
        Base input data directory.

    Returns
    -------
    list[tuple[pathlib.Path, str]]
        Pairs containing the source path and the target filename to place in
        the runtime directory.

    Raises
    ------
    None

    Notes
    -----
    ``physics_files`` may be disabled with ``false`` in ``runtime.yaml``. When
    configured as a mapping, it may provide a custom ``root`` and ``files``
    list. Otherwise, the validated default MPAS physics lookup file list is
    used.

    See Also
    --------
    DEFAULT_MPAS_PHYSICS_FILES : Default MPAS physics lookup files.
    prepare_runtime : Stage the returned file links.

    Examples
    --------
    >>> links = _physics_file_links(False, Path("/data"))
    >>> links
    []
    >>> links = _physics_file_links({}, Path("/data"))
    >>> links[0][1]
    'CAM_ABS_DATA.DBL'
    """
    physics_cfg = runtime_cfg.get("physics_files", {})

    if physics_cfg is False:
        return []

    if isinstance(physics_cfg, dict):
        root = Path(str(physics_cfg.get("root", data_root / "MPAS_namelist_stream_physics_files")))
        files = physics_cfg.get("files", DEFAULT_MPAS_PHYSICS_FILES)
    else:
        root = data_root / "MPAS_namelist_stream_physics_files"
        files = DEFAULT_MPAS_PHYSICS_FILES

    # The target name is only the basename expected in the execution directory,
    # while the source may live under a shared input-data tree.
    return [(root / str(filename), str(filename)) for filename in files]


def prepare_runtime(config: ExperimentConfig) -> list[str]:
    """Create runtime directories and symlinks declared in ``runtime.yaml``.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded and preferably validated experiment configuration.

    Returns
    -------
    list[str]
        Status messages describing created directories and staged links.

    Raises
    ------
    FileNotFoundError
        If a configured source file or directory does not exist.
    FileExistsError
        If a target exists as a real file or directory instead of a symlink.
    KeyError
        If required runtime fields are missing.
    TypeError
        If an entry in ``runtime.required_links`` is not a mapping.

    Notes
    -----
    The function stages data using symbolic links to avoid duplicating large
    NetCDF, HDF5 or MPAS lookup files. This is important in HPC environments
    where input datasets are shared and runtime directories should remain
    lightweight.

    See Also
    --------
    get_data_root : Resolve relative runtime sources.
    get_runtime_dir : Resolve the runtime directory.
    _link_or_keep : Create idempotent symbolic links.

    Examples
    --------
    >>> callable(prepare_runtime)
    True
    """
    runtime_cfg = require_key(config.runtime, "runtime", "runtime.yaml")
    required_dirs = require_key(runtime_cfg, "required_directories", "runtime.yaml")
    required_links = require_key(runtime_cfg, "required_links", "runtime.yaml")

    data_root = get_data_root(config)
    runtime_dir = get_runtime_dir(config)

    messages: list[str] = []
    runtime_dir.mkdir(parents=True, exist_ok=True)
    messages.append(f"[OK] runtime directory: {runtime_dir}")

    # Create the directory skeleton before links are staged. This keeps link
    # creation simple and mirrors the layout required by MPAS-JEDI.
    for directory in required_dirs:
        path = runtime_dir / str(directory)
        path.mkdir(parents=True, exist_ok=True)
        messages.append(f"[OK] directory: {path}")

    for item in required_links:
        if not isinstance(item, dict):
            raise TypeError("Each runtime.required_links entry must be a mapping")

        source = _resolve_source(
            str(require_key(item, "source", "runtime.required_links")), data_root
        )
        target = _resolve_target(
            str(require_key(item, "target", "runtime.required_links")), runtime_dir
        )
        messages.append(_link_or_keep(source, target))

    # MPAS physics lookup tables are staged at the top level of the runtime
    # directory because MPAS reads them relative to the execution working
    # directory.
    for source, target_name in _physics_file_links(runtime_cfg, data_root):
        target = runtime_dir / target_name
        messages.append(_link_or_keep(source, target))

    return messages
