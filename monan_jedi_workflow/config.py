"""Experiment configuration loading and validation.

This module centralizes the configuration contract used by the minimal
MONAN-JEDI MPAS 3D-FGAT baseline workflow. It loads the split YAML files,
stores them in a typed dataclass, and validates the assumptions required by
the current operational baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .yaml_utils import load_yaml_file


# Mapping between the internal configuration section names and the YAML files
# expected in each experiment directory. Keeping the filenames in one place
# makes it easier to evolve the configuration layout without scattering string
# literals throughout the package.
REQUIRED_CONFIG_FILES = {
    "experiment": "experiment.yaml",
    "runtime": "runtime.yaml",
    "variables": "variables.yaml",
    "observations": "observations.yaml",
    "pbs": "pbs.yaml",
}


@dataclass(frozen=True)
class ExperimentConfig:
    """Container for the split experiment configuration files.

    Parameters
    ----------
    root : pathlib.Path
        Absolute path to the directory containing the experiment YAML files.
    experiment : dict[str, typing.Any]
        Parsed content from ``experiment.yaml``. This file defines the
        experiment identity, cycle metadata, geometry, method, paths and JEDI
        executable settings.
    runtime : dict[str, typing.Any]
        Parsed content from ``runtime.yaml``. This file defines directories,
        symbolic links and runtime staging requirements.
    variables : dict[str, typing.Any]
        Parsed content from ``variables.yaml``. This file defines analysis,
        model and background state variables.
    observations : dict[str, typing.Any]
        Parsed content from ``observations.yaml``. This file defines the
        observation spaces, operators and filters rendered into the JEDI YAML.
    pbs : dict[str, typing.Any]
        Parsed content from ``pbs.yaml``. This file defines the PBS job
        resources, runtime environment and logging options.

    Returns
    -------
    ExperimentConfig
        Frozen dataclass instance grouping all split configuration mappings.

    Raises
    ------
    None

    Notes
    -----
    The dataclass is frozen so downstream functions cannot accidentally mutate
    the loaded configuration while rendering files or preparing runtime inputs.
    This is useful in scientific workflows because reproducibility depends on
    preserving the exact configuration state used to generate an experiment.

    See Also
    --------
    load_experiment_config : Load all required YAML files into this container.
    validate_experiment_config : Validate the supported baseline contract.

    Examples
    --------
    >>> from pathlib import Path
    >>> cfg = ExperimentConfig(
    ...     root=Path("/tmp/exp"),
    ...     experiment={"experiment": {"name": "demo"}},
    ...     runtime={"runtime": {}},
    ...     variables={},
    ...     observations={"observers": []},
    ...     pbs={"pbs": {}},
    ... )
    >>> cfg.name
    'demo'
    """

    root: Path
    experiment: dict[str, Any]
    runtime: dict[str, Any]
    variables: dict[str, Any]
    observations: dict[str, Any]
    pbs: dict[str, Any]

    @property
    def name(self) -> str:
        """Return the experiment name from ``experiment.yaml``.

        Parameters
        ----------
        None

        Returns
        -------
        str
            Experiment name stored under ``experiment.name``.

        Raises
        ------
        KeyError
            If either ``experiment`` or ``experiment.name`` is missing.

        Notes
        -----
        The property intentionally reads from the original mapping instead of
        duplicating the value. This keeps the dataclass lightweight and avoids
        two sources of truth for the experiment identifier.

        See Also
        --------
        load_experiment_config : Create an ``ExperimentConfig`` instance.

        Examples
        --------
        >>> from pathlib import Path
        >>> cfg = ExperimentConfig(
        ...     root=Path("."),
        ...     experiment={"experiment": {"name": "case_a"}},
        ...     runtime={},
        ...     variables={},
        ...     observations={},
        ...     pbs={},
        ... )
        >>> cfg.name
        'case_a'
        """
        return str(self.experiment["experiment"]["name"])


def load_experiment_config(config_dir: Path) -> ExperimentConfig:
    """Load all YAML files that define one experiment.

    Parameters
    ----------
    config_dir : pathlib.Path
        Directory containing the required configuration files listed in
        ``REQUIRED_CONFIG_FILES``.

    Returns
    -------
    ExperimentConfig
        Configuration container with one dictionary per split YAML file.

    Raises
    ------
    FileNotFoundError
        If any required YAML file does not exist.
    TypeError
        If a YAML file does not contain a top-level mapping.

    Notes
    -----
    The input directory is resolved before loading files. As a result,
    downstream path calculations can rely on ``config.root`` being absolute,
    even when the user passes a relative path from the command line.

    See Also
    --------
    load_yaml_file : Load and validate a single YAML mapping.
    validate_experiment_config : Validate the loaded configuration.

    Examples
    --------
    >>> sorted(REQUIRED_CONFIG_FILES)
    ['experiment', 'observations', 'pbs', 'runtime', 'variables']
    """
    config_dir = config_dir.resolve()

    loaded: dict[str, dict[str, Any]] = {}

    # Load the split configuration deterministically. The order is useful when
    # debugging because a missing or malformed file is reported consistently.
    for key, filename in REQUIRED_CONFIG_FILES.items():
        loaded[key] = load_yaml_file(config_dir / filename)

    return ExperimentConfig(
        root=config_dir,
        experiment=loaded["experiment"],
        runtime=loaded["runtime"],
        variables=loaded["variables"],
        observations=loaded["observations"],
        pbs=loaded["pbs"],
    )


def require_key(mapping: dict[str, Any], key: str, context: str) -> Any:
    """Return a required key or raise a descriptive error.

    Parameters
    ----------
    mapping : dict[str, typing.Any]
        Mapping to inspect.
    key : str
        Required key name.
    context : str
        Human-readable description of the file or section being checked.

    Returns
    -------
    typing.Any
        Value associated with ``key``.

    Raises
    ------
    KeyError
        If ``key`` is absent from ``mapping``.

    Notes
    -----
    This helper improves diagnostics by attaching configuration context to the
    exception. For example, an error in ``experiment.yaml paths`` is easier to
    fix than a generic missing-key traceback.

    See Also
    --------
    validate_experiment_config : Main consumer of this helper.

    Examples
    --------
    >>> require_key({"mesh": "x1.10242"}, "mesh", "geometry")
    'x1.10242'
    >>> require_key({"mesh": "x1.10242"}, "np", "geometry")
    Traceback (most recent call last):
    ...
    KeyError: "Missing required key 'np' in geometry"
    """
    if key not in mapping:
        raise KeyError(f"Missing required key '{key}' in {context}")
    return mapping[key]


def validate_experiment_config(config: ExperimentConfig) -> list[str]:
    """Validate the initial minimal 3D-FGAT MPASstatic experiment contract.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    list[str]
        Human-readable validation messages describing the checked baseline
        assumptions.

    Raises
    ------
    KeyError
        If a required section or field is missing.
    ValueError
        If a value differs from the currently supported 3D-FGAT MPASstatic
        x1.10242 baseline contract.

    Notes
    -----
    This validator is deliberately strict. The current workflow represents a
    reproducible baseline rather than a fully generic experiment generator.
    Fixed checks, such as mesh size, number of variables and observer ordering,
    protect the rendering layer from producing YAML that appears valid but does
    not match the manually validated MPAS-JEDI reference case.

    See Also
    --------
    ExperimentConfig : Container passed to the validator.
    require_key : Helper used to report missing configuration fields.

    Examples
    --------
    >>> isinstance(validate_experiment_config, object)
    True
    >>> "experiment" in REQUIRED_CONFIG_FILES
    True
    """
    messages: list[str] = []

    # Top-level sections from experiment.yaml. They are checked first because
    # most other validation rules depend on these core scientific assumptions.
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    cycle = require_key(config.experiment, "cycle", "experiment.yaml")
    geometry = require_key(config.experiment, "geometry", "experiment.yaml")
    method = require_key(config.experiment, "method", "experiment.yaml")
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    jedi = require_key(config.experiment, "jedi", "experiment.yaml")

    # Other split configuration files. The renderer assumes these structures
    # exist, so validation fails early when the configuration layout is wrong.
    runtime = require_key(config.runtime, "runtime", "runtime.yaml")
    variables = config.variables
    observations = require_key(config.observations, "observers", "observations.yaml")
    pbs = require_key(config.pbs, "pbs", "pbs.yaml")

    if experiment.get("name") != "3dfgat_mpastatic_x1.10242_2018041500":
        raise ValueError(f"Unexpected experiment name: {experiment.get('name')}")

    if method.get("cost_type") != "3D-FGAT":
        raise ValueError(f"Expected cost_type 3D-FGAT, got {method.get('cost_type')}")

    if method.get("covariance_model") != "MPASstatic":
        raise ValueError(
            f"Expected covariance_model MPASstatic, got {method.get('covariance_model')}"
        )

    if method.get("covariance_date") != "2018-04-14T21:00:00Z":
        raise ValueError(
            "Expected covariance_date 2018-04-14T21:00:00Z, "
            f"got {method.get('covariance_date')}"
        )

    if geometry.get("mesh") != "x1.10242":
        raise ValueError(f"Expected mesh x1.10242, got {geometry.get('mesh')}")

    if int(geometry.get("np", -1)) != 64:
        raise ValueError(f"Expected geometry.np 64, got {geometry.get('np')}")

    if int(pbs.get("mpiprocs", -1)) != 64:
        raise ValueError(f"Expected pbs.mpiprocs 64, got {pbs.get('mpiprocs')}")

    analysis_variables = require_key(variables, "analysis_variables", "variables.yaml")
    model_variables = require_key(variables, "model_variables", "variables.yaml")
    state_variables = require_key(
        variables, "background_state_variables", "variables.yaml"
    )

    # The baseline uses a compact increment control vector but a larger MPAS
    # state vector. These counts are part of the scientific contract because
    # variable ordering and dimensions affect MPAS-JEDI linear algebra.
    if len(analysis_variables) != 5:
        raise ValueError(f"Expected 5 analysis variables, got {len(analysis_variables)}")

    if len(model_variables) != 30:
        raise ValueError(f"Expected 30 model variables, got {len(model_variables)}")

    if len(state_variables) != 30:
        raise ValueError(
            f"Expected 30 background state variables, got {len(state_variables)}"
        )

    if model_variables != state_variables:
        raise ValueError("model_variables and background_state_variables must match")

    # Observer order is preserved in the rendered YAML. Keeping it deterministic
    # makes diffs against the reference baseline easier to inspect.
    observer_names = [item.get("name") for item in observations]
    expected_observers = ["Radiosonde", "GnssroRefNCEP", "SfcCorrected"]
    if observer_names != expected_observers:
        raise ValueError(
            f"Expected observers {expected_observers}, got {observer_names}"
        )

    required_links = require_key(runtime, "required_links", "runtime.yaml")
    required_directories = require_key(runtime, "required_directories", "runtime.yaml")
    stream_required = require_key(
        runtime, "stream_background_required_fields", "runtime.yaml"
    )
    required_xtime = require_key(runtime, "required_xtime", "runtime.yaml")

    if not required_links:
        raise ValueError("runtime.required_links cannot be empty")

    # These directories mirror the runtime layout expected by the MPAS-JEDI
    # application and the validated manual execution directory.
    for directory in ["background", "Data/os", "Data/states", "testinput"]:
        if directory not in required_directories:
            raise ValueError(f"runtime.required_directories must include {directory}")

    # Surface and land-use fields are required because the MPAS static B
    # configuration and operators expect them to be present in background files.
    for field in ["ivgtyp", "isltyp", "landmask", "znt", "t2m"]:
        if field not in stream_required:
            raise ValueError(
                f"runtime.stream_background_required_fields missing {field}"
            )

    for required in [
        "background/mpasout.2018-04-14_21.00.00.nc",
        "templateFields.10242.nc",
    ]:
        if required not in required_xtime:
            raise ValueError(f"runtime.required_xtime missing {required}")

    # Paths and executable are checked last because they are mostly operational
    # settings. They are still required before rendering or staging files.
    for key in ["data_root", "work_root", "runtime_dir", "rendered_dir", "scratch_root"]:
        require_key(paths, key, "experiment.yaml paths")

    require_key(jedi, "executable", "experiment.yaml jedi")

    messages.append(f"experiment: {experiment['name']}")
    messages.append(f"cycle: {cycle['id']}")
    messages.append("method: 3D-FGAT + MPASstatic")
    messages.append("mesh: x1.10242")
    messages.append("np: 64")
    messages.append("analysis variables: 5")
    messages.append("model variables: 30")
    messages.append("background state variables: 30")
    messages.append("observers: Radiosonde, GnssroRefNCEP, SfcCorrected")
    messages.append("configuration contract: OK")

    return messages
