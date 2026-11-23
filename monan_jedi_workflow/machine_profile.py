"""Machine-independent computational profile contract.

A machine profile describes *where/how* to execute, never scientific choices.
This module performs no machine discovery, job submission, or file mutation.
It is deliberately independent of JACI, Spack, Conda, PBS, and MPAS-JEDI.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import os
import re

import yaml


class MachineProfileError(ValueError):
    """The supplied computational profile is malformed or inconsistent."""


_PATH_KEYS = frozenset({
    "work_root", "scratch_root", "installation_root", "stack_root",
    "mesh_root", "physics_root", "bmatrix_root", "observations_root",
    "gfs_root", "libfabric_root",
})
_ENV_KINDS = frozenset({"native", "modules"})
_BACKENDS = frozenset({"local", "pbs", "slurm"})
_ENV_VAR = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class MachineProfile:
    source: Path
    name: str
    backend: str
    environment_kind: str
    paths: Mapping[str, Path]
    execution: Mapping[str, Any]
    environment: Mapping[str, Any]

    def describe(self) -> dict[str, Any]:
        """Return a JSON/YAML-serializable, normalized view."""
        return {
            "schema_version": 1,
            "machine": {"name": self.name},
            "paths": {key: str(value) for key, value in self.paths.items()},
            "execution": dict(self.execution),
            "environment": dict(self.environment),
        }


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MachineProfileError(f"{field} must be a YAML mapping")
    return value


def _path(value: Any, *, field: str, env: Mapping[str, str],
          require_existing: bool) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise MachineProfileError(f"{field} must be a nonempty path")
    # Resolve only explicitly supplied environment variables.
    def replace(match: re.Match[str]) -> str:
        variable = match.group(1) or match.group(2)
        if variable not in env:
            raise MachineProfileError(
                f"{field} references undefined environment variable {variable}"
            )
        return env[variable]
    expanded = _ENV_VAR.sub(replace, value)
    candidate = Path(expanded).expanduser()
    if not candidate.is_absolute():
        raise MachineProfileError(
            f"{field} must be an absolute path (received {value!r})"
        )
    resolved = candidate.resolve(strict=False)
    if require_existing and not resolved.is_dir():
        raise MachineProfileError(
            f"{field} directory does not exist: {resolved}"
        )
    return resolved


def load_machine_profile(
    path: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
    require_existing: bool = False,
) -> MachineProfile:
    """Read and validate a machine profile (schema 1).

    Validation is read-only and does not require scientific binaries. The
    optional existence check verifies *directories only*, not MPI/DA science.
    """
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Machine profile not found: {source}")
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MachineProfileError(f"Invalid YAML at {source}: {exc}") from exc
    root = _mapping(payload, "machine profile")
    allowed = {"schema_version", "machine", "paths", "execution", "environment"}
    unknown = set(root) - allowed
    if unknown:
        raise MachineProfileError(
            f"Unsupported machine profile keys: {', '.join(sorted(unknown))}"
        )
    if root.get("schema_version") != 1 or isinstance(root.get("schema_version"), bool):
        raise MachineProfileError("machine profile schema_version must be 1")

    machine = _mapping(root.get("machine"), "machine")
    if set(machine) != {"name"}:
        raise MachineProfileError("machine must define only the name field")
    name = machine["name"]
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise MachineProfileError("machine.name must be a nonempty simple identifier")

    execution = _mapping(root.get("execution"), "execution")
    backend = execution.get("backend")
    if backend not in _BACKENDS:
        raise MachineProfileError("execution.backend must be local, pbs or slurm")
    if set(execution) - {"backend", "queue", "max_cores", "walltime"}:
        raise MachineProfileError("Unsupported execution fields")
    if backend == "local" and ("queue" in execution or "walltime" in execution):
        raise MachineProfileError(
            "local execution cannot define a scheduler queue or walltime"
        )
    if "queue" in execution and (not isinstance(execution["queue"], str)
                                  or not execution["queue"].strip()):
        raise MachineProfileError("execution.queue must be nonempty")
    if "max_cores" in execution and (
        type(execution["max_cores"]) is not int or execution["max_cores"] <= 0
    ):
        raise MachineProfileError("execution.max_cores must be a positive integer")
    if "walltime" in execution and (
        not isinstance(execution["walltime"], str)
        or not re.fullmatch(r"\d{1,3}:[0-5]\d:[0-5]\d", execution["walltime"])
    ):
        raise MachineProfileError("execution.walltime must be HH:MM:SS")

    environment = _mapping(root.get("environment"), "environment")
    kind = environment.get("kind")
    if kind not in _ENV_KINDS:
        raise MachineProfileError("environment.kind must be native or modules")
    if set(environment) - {"kind", "setup"}:
        raise MachineProfileError("Unsupported environment fields")
    if kind == "native" and "setup" in environment:
        raise MachineProfileError("native environment cannot define modules setup")

    variables = dict(os.environ if environ is None else environ)
    raw_paths = _mapping(root.get("paths"), "paths")
    if set(raw_paths) - _PATH_KEYS:
        raise MachineProfileError(
            "Unsupported path keys: " + ", ".join(sorted(set(raw_paths) - _PATH_KEYS))
        )
    if "work_root" not in raw_paths:
        raise MachineProfileError("paths.work_root is required")
    paths = {
        name: _path(value, field=f"paths.{name}", env=variables,
                    require_existing=require_existing)
        for name, value in raw_paths.items()
    }
    if kind == "modules":
        if "setup" not in environment:
            raise MachineProfileError("environment.setup is required for modules")
        setup = _path(environment["setup"], field="environment.setup",
                      env=variables, require_existing=False)
        if require_existing and not setup.is_file():
            raise MachineProfileError(f"environment.setup file does not exist: {setup}")
        environment = {**environment, "setup": str(setup)}
    return MachineProfile(
        source=source, name=name, backend=backend, environment_kind=kind,
        paths=paths, execution=dict(execution), environment=dict(environment),
    )
