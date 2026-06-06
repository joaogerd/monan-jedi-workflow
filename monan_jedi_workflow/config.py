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

OPTIONAL_CONFIG_FILES = {
    "validation": "validation.yaml",
}

DEFAULT_BASELINE_EXPECTED = {
    "experiment_name": "3dfgat_mpastatic_x1.10242_2018041500",
    "cost_type": "3D-FGAT",
    "covariance_model": "MPASstatic",
    "covariance_date": "2018-04-14T21:00:00Z",
    "mesh": "x1.10242",
    "np": 64,
    "mpiprocs": 64,
    "analysis_variables_count": 5,
    "model_variables_count": 30,
    "background_state_variables_count": 30,
    "observers": ["Radiosonde", "GnssroRefNCEP", "SfcCorrected"],
    "required_runtime_directories": [
        "background",
        "Data/os",
        "Data/states",
        "testinput",
    ],
    "required_background_fields": ["ivgtyp", "isltyp", "landmask", "znt", "t2m"],
    "required_xtime_files": [
        "background/mpasout.2018-04-14_21.00.00.nc",
        "templateFields.10242.nc",
    ],
}


@dataclass(frozen=True)
class ExperimentConfig:
    """Container for the split experiment configuration files."""

    root: Path
    experiment: dict[str, Any]
    runtime: dict[str, Any]
    variables: dict[str, Any]
    observations: dict[str, Any]
    pbs: dict[str, Any]
    validation: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        """Return the experiment name from ``experiment.yaml``."""
        return str(self.experiment["experiment"]["name"])


def load_experiment_config(config_dir: Path) -> ExperimentConfig:
    """Load all YAML files that define one experiment.

    Required files are listed in ``REQUIRED_CONFIG_FILES``. Optional files, such
    as ``validation.yaml``, are loaded when present and ignored otherwise. This
    preserves compatibility with older experiment directories while allowing new
    experiments to make their validation contract explicit.
    """
    config_dir = config_dir.resolve()

    loaded: dict[str, dict[str, Any]] = {}

    # Load the split configuration deterministically. The order is useful when
    # debugging because a missing or malformed file is reported consistently.
    for key, filename in REQUIRED_CONFIG_FILES.items():
        loaded[key] = load_yaml_file(config_dir / filename)

    optional: dict[str, dict[str, Any] | None] = {}
    for key, filename in OPTIONAL_CONFIG_FILES.items():
        path = config_dir / filename
        optional[key] = load_yaml_file(path) if path.is_file() else None

    return ExperimentConfig(
        root=config_dir,
        experiment=loaded["experiment"],
        runtime=loaded["runtime"],
        variables=loaded["variables"],
        observations=loaded["observations"],
        pbs=loaded["pbs"],
        validation=optional["validation"],
    )


def require_key(mapping: dict[str, Any], key: str, context: str) -> Any:
    """Return a required key or raise a descriptive error."""
    if key not in mapping:
        raise KeyError(f"Missing required key '{key}' in {context}")
    return mapping[key]


def _expected_from_validation(config: ExperimentConfig) -> tuple[str, dict[str, Any]]:
    """Return the validation profile and expected baseline contract.

    ``validation.yaml`` is the preferred source of truth. When it is absent, the
    original strict baseline defaults are used so existing experiments keep the
    same behavior until they adopt a declarative contract.
    """
    if config.validation is None:
        return "strict_baseline:builtin", dict(DEFAULT_BASELINE_EXPECTED)

    validation = require_key(config.validation, "validation", "validation.yaml")
    profile = str(validation.get("profile", "strict_baseline"))
    expected = require_key(validation, "expected", "validation.yaml validation")

    merged = dict(DEFAULT_BASELINE_EXPECTED)
    merged.update(expected)
    return profile, merged


def _assert_equal(actual: Any, expected: Any, label: str) -> None:
    """Raise ``ValueError`` when a value differs from the validation contract."""
    if actual != expected:
        raise ValueError(f"Expected {label} {expected!r}, got {actual!r}")


def _assert_int_equal(actual: Any, expected: Any, label: str) -> None:
    """Compare integer-like values with a clear diagnostic."""
    try:
        actual_int = int(actual)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected {label} to be integer-like, got {actual!r}") from exc

    _assert_equal(actual_int, int(expected), label)


def _assert_sequence_equal(actual: list[Any], expected: list[Any], label: str) -> None:
    """Compare ordered lists from configuration and validation contract."""
    if actual != expected:
        raise ValueError(f"Expected {label} {expected!r}, got {actual!r}")


def validate_experiment_config(config: ExperimentConfig) -> list[str]:
    """Validate the initial minimal 3D-FGAT MPASstatic experiment contract.

    The validation is intentionally strict, but the strict values are now read
    from ``validation.yaml`` when that file is present. This keeps the validated
    baseline protected while making the contract explicit and reviewable.
    """
    messages: list[str] = []
    profile, expected = _expected_from_validation(config)

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

    _assert_equal(experiment.get("name"), expected["experiment_name"], "experiment.name")
    _assert_equal(method.get("cost_type"), expected["cost_type"], "method.cost_type")
    _assert_equal(
        method.get("covariance_model"),
        expected["covariance_model"],
        "method.covariance_model",
    )
    _assert_equal(
        method.get("covariance_date"),
        expected["covariance_date"],
        "method.covariance_date",
    )
    _assert_equal(geometry.get("mesh"), expected["mesh"], "geometry.mesh")
    _assert_int_equal(geometry.get("np", -1), expected["np"], "geometry.np")
    _assert_int_equal(pbs.get("mpiprocs", -1), expected["mpiprocs"], "pbs.mpiprocs")

    analysis_variables = require_key(variables, "analysis_variables", "variables.yaml")
    model_variables = require_key(variables, "model_variables", "variables.yaml")
    state_variables = require_key(
        variables,
        "background_state_variables",
        "variables.yaml",
    )

    _assert_int_equal(
        len(analysis_variables),
        expected["analysis_variables_count"],
        "analysis_variables count",
    )
    _assert_int_equal(
        len(model_variables),
        expected["model_variables_count"],
        "model_variables count",
    )
    _assert_int_equal(
        len(state_variables),
        expected["background_state_variables_count"],
        "background_state_variables count",
    )

    if model_variables != state_variables:
        raise ValueError("model_variables and background_state_variables must match")

    # Observer order is preserved in the rendered YAML. Keeping it deterministic
    # makes diffs against the reference baseline easier to inspect.
    observer_names = [item.get("name") for item in observations]
    _assert_sequence_equal(observer_names, expected["observers"], "observers")

    required_links = require_key(runtime, "required_links", "runtime.yaml")
    required_directories = require_key(runtime, "required_directories", "runtime.yaml")
    stream_required = require_key(
        runtime,
        "stream_background_required_fields",
        "runtime.yaml",
    )
    required_xtime = require_key(runtime, "required_xtime", "runtime.yaml")

    if not required_links:
        raise ValueError("runtime.required_links cannot be empty")

    for directory in expected["required_runtime_directories"]:
        if directory not in required_directories:
            raise ValueError(f"runtime.required_directories must include {directory}")

    for field in expected["required_background_fields"]:
        if field not in stream_required:
            raise ValueError(
                f"runtime.stream_background_required_fields missing {field}"
            )

    for required in expected["required_xtime_files"]:
        if required not in required_xtime:
            raise ValueError(f"runtime.required_xtime missing {required}")

    # Paths and executable are checked last because they are mostly operational
    # settings. They are still required before rendering or staging files.
    for key in ["data_root", "work_root", "runtime_dir", "rendered_dir", "scratch_root"]:
        require_key(paths, key, "experiment.yaml paths")

    require_key(jedi, "executable", "experiment.yaml jedi")

    messages.append(f"experiment: {experiment['name']}")
    messages.append(f"cycle: {cycle['id']}")
    messages.append(f"validation profile: {profile}")
    messages.append(
        f"method: {expected['cost_type']} + {expected['covariance_model']}"
    )
    messages.append(f"mesh: {expected['mesh']}")
    messages.append(f"np: {expected['np']}")
    messages.append(f"analysis variables: {expected['analysis_variables_count']}")
    messages.append(f"model variables: {expected['model_variables_count']}")
    messages.append(
        f"background state variables: {expected['background_state_variables_count']}"
    )
    messages.append(f"observers: {', '.join(expected['observers'])}")
    messages.append("configuration contract: OK")

    return messages
