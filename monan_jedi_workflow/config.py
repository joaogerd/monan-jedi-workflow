"""Experiment configuration loading and validation.

This module centralizes the configuration contract used by the minimal
MONAN-JEDI MPAS 3D-FGAT baseline workflow. It loads the split YAML files,
stores them in a typed dataclass, resolves reusable JEDI fragments, and
validates the assumptions required by the selected validation profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fragments import resolve_observation_config, resolve_variable_config
from .yaml_utils import load_yaml_file


# Mapping between the internal configuration section names and the YAML files
# expected in each experiment directory. The validation file is intentionally
# part of the required split configuration because it stores experiment-specific
# scientific and operational contracts that should not be duplicated in Python.
REQUIRED_CONFIG_FILES = {
    "experiment": "experiment.yaml",
    "runtime": "runtime.yaml",
    "variables": "variables.yaml",
    "observations": "observations.yaml",
    "pbs": "pbs.yaml",
    "validation": "validation.yaml",
}


@dataclass(frozen=True)
class ExperimentConfig:
    """Container for the split experiment configuration files.

    Parameters
    ----------
    root : pathlib.Path
        Absolute path to the directory containing the experiment YAML files.
    experiment : dict[str, typing.Any]
        Parsed content from ``experiment.yaml``.
    runtime : dict[str, typing.Any]
        Parsed content from ``runtime.yaml``.
    variables : dict[str, typing.Any]
        Parsed and fragment-resolved content from ``variables.yaml``.
    observations : dict[str, typing.Any]
        Parsed and fragment-resolved content from ``observations.yaml``.
    pbs : dict[str, typing.Any]
        Parsed content from ``pbs.yaml``.
    validation : dict[str, typing.Any]
        Parsed content from ``validation.yaml``. This file defines the expected
        values used by the validator.

    Returns
    -------
    ExperimentConfig
        Frozen dataclass instance grouping all split configuration mappings.

    Raises
    ------
    None

    Notes
    -----
    Keeping validation expectations in ``validation.yaml`` avoids hardcoding
    experiment-specific values such as mesh name, processor count, variable
    counts, observer ordering and runtime field requirements in this module.
    The Python code remains responsible for the validation algorithm, while the
    YAML file remains responsible for the validation data.

    See Also
    --------
    load_experiment_config : Load all required YAML files into this container.
    validate_experiment_config : Validate a loaded experiment configuration.

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
    ...     validation={"validation": {"expected": {}}},
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
    validation: dict[str, Any]

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
        ...     validation={},
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
    KeyError
        If a compact variable or observation selector references a missing
        reusable fragment.

    Notes
    -----
    ``variables.yaml`` and ``observations.yaml`` may contain either fully
    expanded structures or compact selector syntax that points to reusable
    fragments under ``configs/fragments/jedi``. Fragment resolution happens
    immediately after loading so validation and rendering always receive the
    expanded form.

    See Also
    --------
    load_yaml_file : Load and validate a single YAML mapping.
    validate_experiment_config : Validate the loaded configuration.

    Examples
    --------
    >>> sorted(REQUIRED_CONFIG_FILES)
    ['experiment', 'observations', 'pbs', 'runtime', 'validation', 'variables']
    """
    config_dir = config_dir.resolve()

    loaded: dict[str, dict[str, Any]] = {}

    # Load the split configuration deterministically. The order is useful when
    # debugging because a missing or malformed file is reported consistently.
    for key, filename in REQUIRED_CONFIG_FILES.items():
        loaded[key] = load_yaml_file(config_dir / filename)

    # Preserve the existing fragment-resolution behavior from main. The
    # validation refactor must not regress compact fragment support.
    loaded["variables"] = resolve_variable_config(
        config_dir, loaded["variables"]
    )
    loaded["observations"] = resolve_observation_config(
        config_dir, loaded["observations"]
    )

    return ExperimentConfig(
        root=config_dir,
        experiment=loaded["experiment"],
        runtime=loaded["runtime"],
        variables=loaded["variables"],
        observations=loaded["observations"],
        pbs=loaded["pbs"],
        validation=loaded["validation"],
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


def require_non_empty_list(value: Any, context: str) -> list[Any]:
    """Validate and return a non-empty YAML list.

    Parameters
    ----------
    value : typing.Any
        Value loaded from a YAML configuration file.
    context : str
        Human-readable configuration key used in diagnostic messages.

    Returns
    -------
    list[typing.Any]
        The original list after structural validation.

    Raises
    ------
    TypeError
        If ``value`` is not a Python list.
    ValueError
        If ``value`` is an empty list.

    Notes
    -----
    This helper intentionally validates only the structure of configurable
    collections. It does not encode scientific or MPAS-JEDI-specific field
    names. Those field names belong in YAML so that the configuration remains
    the single source of truth for domain contracts that may evolve between
    experiments.

    See Also
    --------
    require_key : Fetch required mapping entries with contextual errors.
    validate_experiment_config : Use this helper for runtime list contracts.

    Examples
    --------
    >>> require_non_empty_list(["ivgtyp", "landmask"], "runtime.fields")
    ['ivgtyp', 'landmask']
    >>> require_non_empty_list([], "runtime.fields")
    Traceback (most recent call last):
    ...
    ValueError: runtime.fields cannot be empty
    """
    if not isinstance(value, list):
        raise TypeError(f"{context} must be a YAML list")

    if not value:
        raise ValueError(f"{context} cannot be empty")

    return value


def validate_equal(actual: Any, expected: Any, context: str) -> None:
    """Validate exact equality between an actual and expected value.

    Parameters
    ----------
    actual : typing.Any
        Value found in the loaded experiment configuration.
    expected : typing.Any
        Value declared in ``validation.yaml``.
    context : str
        Human-readable name of the validated field.

    Returns
    -------
    None
        The function returns ``None`` when validation succeeds.

    Raises
    ------
    ValueError
        If ``actual`` differs from ``expected``.

    Notes
    -----
    This helper centralizes equality checks so that individual validation rules
    do not repeat error-message formatting. The expected values are supplied by
    configuration, not by hardcoded literals in the validator.

    See Also
    --------
    validate_count : Validate the length of a configured sequence.
    validate_contains_all : Validate that a collection contains required items.

    Examples
    --------
    >>> validate_equal("x1.10242", "x1.10242", "geometry.mesh")
    >>> validate_equal("x1.40962", "x1.10242", "geometry.mesh")
    Traceback (most recent call last):
    ...
    ValueError: Expected geometry.mesh x1.10242, got x1.40962
    """
    if actual != expected:
        raise ValueError(f"Expected {context} {expected}, got {actual}")


def validate_count(items: list[Any], expected_count: int, context: str) -> None:
    """Validate the number of items in a list.

    Parameters
    ----------
    items : list[typing.Any]
        Sequence-like configuration value whose length is checked.
    expected_count : int
        Expected number of elements declared in ``validation.yaml``.
    context : str
        Human-readable name of the validated collection.

    Returns
    -------
    None
        The function returns ``None`` when validation succeeds.

    Raises
    ------
    ValueError
        If ``len(items)`` differs from ``expected_count``.

    Notes
    -----
    Variable counts are part of the current MPAS-JEDI baseline contract because
    the order and dimensionality of analysis, model and background variables
    affect the rendered variational configuration.

    See Also
    --------
    validate_equal : Validate scalar equality.
    validate_sequence_equal : Validate ordered collections.

    Examples
    --------
    >>> validate_count(["u", "v"], 2, "analysis variables")
    >>> validate_count(["u"], 2, "analysis variables")
    Traceback (most recent call last):
    ...
    ValueError: Expected 2 analysis variables, got 1
    """
    actual_count = len(items)

    if actual_count != expected_count:
        raise ValueError(f"Expected {expected_count} {context}, got {actual_count}")


def validate_sequence_equal(
    actual: list[Any],
    expected: list[Any],
    context: str,
) -> None:
    """Validate equality between two ordered lists.

    Parameters
    ----------
    actual : list[typing.Any]
        Ordered values found in the loaded experiment configuration.
    expected : list[typing.Any]
        Ordered values declared in ``validation.yaml``.
    context : str
        Human-readable name of the validated list.

    Returns
    -------
    None
        The function returns ``None`` when validation succeeds.

    Raises
    ------
    ValueError
        If the ordered lists differ.

    Notes
    -----
    This helper is used for observer names because observer order is preserved
    in the rendered JEDI YAML. Deterministic ordering makes diffs against the
    reference baseline easier to inspect.

    See Also
    --------
    validate_contains_all : Validate membership without enforcing order.

    Examples
    --------
    >>> validate_sequence_equal(["a", "b"], ["a", "b"], "observers")
    >>> validate_sequence_equal(["b", "a"], ["a", "b"], "observers")
    Traceback (most recent call last):
    ...
    ValueError: Expected observers ['a', 'b'], got ['b', 'a']
    """
    if actual != expected:
        raise ValueError(f"Expected {context} {expected}, got {actual}")


def validate_contains_all(
    available: list[Any] | dict[Any, Any],
    required: list[Any],
    context: str,
) -> None:
    """Validate that all required items are available.

    Parameters
    ----------
    available : list[typing.Any] or dict[typing.Any, typing.Any]
        Runtime collection from the loaded experiment configuration. Dictionary
        inputs are checked by key, which is useful for ``required_xtime``.
    required : list[typing.Any]
        Required items declared in ``validation.yaml``.
    context : str
        Human-readable name of the validated collection.

    Returns
    -------
    None
        The function returns ``None`` when validation succeeds.

    Raises
    ------
    ValueError
        If any required item is absent from ``available``.

    Notes
    -----
    Membership validation is order-independent. Missing values are sorted to
    keep error messages stable across input ordering and Python versions.

    See Also
    --------
    validate_sequence_equal : Validate ordered lists.

    Examples
    --------
    >>> validate_contains_all(["a", "b"], ["a"], "runtime.items")
    >>> validate_contains_all({"a": 1}, ["a"], "runtime.items")
    >>> validate_contains_all(["a"], ["a", "b"], "runtime.items")
    Traceback (most recent call last):
    ...
    ValueError: runtime.items missing required items: b
    """
    available_items = set(available.keys()) if isinstance(available, dict) else set(available)
    missing = sorted(set(required) - available_items)

    if missing:
        missing_text = ", ".join(str(item) for item in missing)
        raise ValueError(f"{context} missing required items: {missing_text}")


def validate_experiment_config(config: ExperimentConfig) -> list[str]:
    """Validate an experiment configuration against ``validation.yaml``.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    list[str]
        Human-readable validation messages describing the checked assumptions.

    Raises
    ------
    KeyError
        If a required section or validation expectation is missing.
    TypeError
        If a runtime list contract is not represented as a YAML list.
    ValueError
        If a value differs from the expectations declared in
        ``validation.yaml``.

    Notes
    -----
    The validator is still strict, but the strict values now come from
    ``validation.yaml``. This separates the validation algorithm from the
    experiment-specific validation data. In practice, the code defines how to
    validate, while the YAML file defines what the selected experiment expects.

    See Also
    --------
    ExperimentConfig : Container passed to the validator.
    require_key : Helper used to report missing configuration fields.
    validate_equal : Helper used for scalar validation rules.
    validate_contains_all : Helper used for membership validation rules.

    Examples
    --------
    >>> isinstance(validate_experiment_config, object)
    True
    >>> "validation" in REQUIRED_CONFIG_FILES
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
    validation = require_key(config.validation, "validation", "validation.yaml")
    expected = require_key(validation, "expected", "validation.yaml validation")

    validate_equal(
        experiment.get("name"),
        require_key(expected, "experiment_name", "validation.yaml expected"),
        "experiment name",
    )
    validate_equal(
        method.get("cost_type"),
        require_key(expected, "cost_type", "validation.yaml expected"),
        "cost_type",
    )
    validate_equal(
        method.get("covariance_model"),
        require_key(expected, "covariance_model", "validation.yaml expected"),
        "covariance_model",
    )
    validate_equal(
        method.get("covariance_date"),
        require_key(expected, "covariance_date", "validation.yaml expected"),
        "covariance_date",
    )
    validate_equal(
        geometry.get("mesh"),
        require_key(expected, "mesh", "validation.yaml expected"),
        "mesh",
    )
    validate_equal(
        int(geometry.get("np", -1)),
        int(require_key(expected, "np", "validation.yaml expected")),
        "geometry.np",
    )
    validate_equal(
        int(pbs.get("mpiprocs", -1)),
        int(require_key(expected, "mpiprocs", "validation.yaml expected")),
        "pbs.mpiprocs",
    )

    analysis_variables = require_key(variables, "analysis_variables", "variables.yaml")
    model_variables = require_key(variables, "model_variables", "variables.yaml")
    state_variables = require_key(
        variables, "background_state_variables", "variables.yaml"
    )

    # The baseline uses a compact increment control vector but a larger MPAS
    # state vector. The expected counts now come from validation.yaml so future
    # experiments can adjust them without changing the validator implementation.
    validate_count(
        analysis_variables,
        int(require_key(expected, "analysis_variables_count", "validation.yaml expected")),
        "analysis variables",
    )
    validate_count(
        model_variables,
        int(require_key(expected, "model_variables_count", "validation.yaml expected")),
        "model variables",
    )
    validate_count(
        state_variables,
        int(require_key(expected, "background_state_variables_count", "validation.yaml expected")),
        "background state variables",
    )

    if model_variables != state_variables:
        raise ValueError("model_variables and background_state_variables must match")

    observer_names = [item.get("name") for item in observations]
    expected_observers = require_non_empty_list(
        require_key(expected, "observers", "validation.yaml expected"),
        "validation.expected.observers",
    )
    validate_sequence_equal(observer_names, expected_observers, "observers")

    required_links = require_key(runtime, "required_links", "runtime.yaml")
    required_directories = require_key(runtime, "required_directories", "runtime.yaml")
    stream_required = require_key(
        runtime, "stream_background_required_fields", "runtime.yaml"
    )
    required_xtime = require_key(runtime, "required_xtime", "runtime.yaml")

    if not required_links:
        raise ValueError("runtime.required_links cannot be empty")

    expected_directories = require_non_empty_list(
        require_key(expected, "required_runtime_directories", "validation.yaml expected"),
        "validation.expected.required_runtime_directories",
    )
    validate_contains_all(
        required_directories,
        expected_directories,
        "runtime.required_directories",
    )

    # The concrete MPAS stream background field names are intentionally kept in
    # YAML. validation.yaml defines the contract; runtime.yaml defines the list
    # that the workflow stages and validates for the selected experiment.
    require_non_empty_list(
        stream_required,
        "runtime.stream_background_required_fields",
    )
    expected_background_fields = require_non_empty_list(
        require_key(expected, "required_background_fields", "validation.yaml expected"),
        "validation.expected.required_background_fields",
    )
    validate_contains_all(
        stream_required,
        expected_background_fields,
        "runtime.stream_background_required_fields",
    )

    # Required xtime file keys are also part of the experiment validation data.
    # Keeping them in validation.yaml avoids embedding cycle-specific filenames
    # in the validator implementation.
    expected_xtime_files = require_non_empty_list(
        require_key(expected, "required_xtime_files", "validation.yaml expected"),
        "validation.expected.required_xtime_files",
    )
    validate_contains_all(
        required_xtime,
        expected_xtime_files,
        "runtime.required_xtime",
    )

    # Paths and executable are checked last because they are mostly operational
    # settings. They are still required before rendering or staging files.
    for key in ["data_root", "work_root", "runtime_dir", "rendered_dir", "scratch_root"]:
        require_key(paths, key, "experiment.yaml paths")

    require_key(jedi, "executable", "experiment.yaml jedi")

    messages.append(f"experiment: {experiment['name']}")
    messages.append(f"cycle: {cycle['id']}")
    messages.append(
        f"method: {method.get('cost_type')} + {method.get('covariance_model')}"
    )
    messages.append(f"mesh: {geometry.get('mesh')}")
    messages.append(f"np: {geometry.get('np')}")
    messages.append(f"analysis variables: {len(analysis_variables)}")
    messages.append(f"model variables: {len(model_variables)}")
    messages.append(f"background state variables: {len(state_variables)}")
    messages.append("observers: " + ", ".join(observer_names))
    messages.append("configuration contract: OK")

    return messages
