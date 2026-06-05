"""Experiment configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .yaml_utils import load_yaml_file


REQUIRED_CONFIG_FILES = {
    "experiment": "experiment.yaml",
    "runtime": "runtime.yaml",
    "variables": "variables.yaml",
    "observations": "observations.yaml",
    "pbs": "pbs.yaml",
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

    @property
    def name(self) -> str:
        return str(self.experiment["experiment"]["name"])


def load_experiment_config(config_dir: Path) -> ExperimentConfig:
    """Load all YAML files that define one experiment."""
    config_dir = config_dir.resolve()

    loaded: dict[str, dict[str, Any]] = {}
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
    """Return a required key or raise a descriptive error."""
    if key not in mapping:
        raise KeyError(f"Missing required key '{key}' in {context}")
    return mapping[key]


def validate_experiment_config(config: ExperimentConfig) -> list[str]:
    """Validate the initial minimal 3DFGAT MPASstatic experiment contract."""
    messages: list[str] = []

    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    cycle = require_key(config.experiment, "cycle", "experiment.yaml")
    geometry = require_key(config.experiment, "geometry", "experiment.yaml")
    method = require_key(config.experiment, "method", "experiment.yaml")
    paths = require_key(config.experiment, "paths", "experiment.yaml")
    jedi = require_key(config.experiment, "jedi", "experiment.yaml")

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

    for directory in ["background", "Data/os", "Data/states", "testinput"]:
        if directory not in required_directories:
            raise ValueError(f"runtime.required_directories must include {directory}")

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
