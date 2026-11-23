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
    # Distinguish the existing JACI site.yaml contract from machine.yaml v1
    # before reporting unrelated unknown keys.
    if root.get("schema_version") != 1 or isinstance(root.get("schema_version"), bool):
        if "site" in root and "stack" in root:
            raise MachineProfileError(
                "Legacy site.yaml is not a machine profile: "
                "machine profile schema_version must be 1. "
                "Continue using experiment create --site for legacy profiles."
            )
        raise MachineProfileError("machine profile schema_version must be 1")
    allowed = {"schema_version", "machine", "paths", "execution", "environment"}
    unknown = set(root) - allowed
    if unknown:
        raise MachineProfileError(
            f"Unsupported machine profile keys: {', '.join(sorted(unknown))}"
        )

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


# Transitional adapter: the scientific PBS stages still consume the legacy
# site/stack/jedi/environment structure. Do not put scientific choices here.
_PBS_LEGACY_PATHS = {
    "installation_root": "MONAN_JEDI_INSTALL_ROOT",
    "stack_root": "STACK_ROOT",
    "mesh_root": "MONAN_MESH_ROOT",
    "physics_root": "MONAN_PHYSICS_ROOT",
    "bmatrix_root": "MONAN_BMATRIX_ROOT",
    "observations_root": "MONAN_INPUT_ROOT",
    "gfs_root": "MONAN_GFS_ROOT",
    "libfabric_root": "MONAN_LIBFABRIC_ROOT",
}


def machine_to_legacy_site(profile: MachineProfile) -> dict[str, Any]:
    """Translate a *complete PBS* machine profile to the existing site API.

    Strictly reject incomplete/local/slurm profiles: the current scientific
    stages are PBS-only and silently generating PBS from a local profile would
    violate the user's selected computing environment.
    """
    if profile.backend != "pbs":
        raise MachineProfileError(
            f"Machine backend {profile.backend!r} cannot create a scientific case yet: "
            "current MPAS/JEDI/WPS/Obs2IODA stages require native PBS. "
            "Machine profiles can still be validated with experiment machine validate."
        )
    if profile.environment_kind != "modules":
        raise MachineProfileError(
            "Scientific PBS case currently requires environment.kind: modules"
        )
    missing = sorted(set(_PBS_LEGACY_PATHS) - set(profile.paths))
    if missing:
        raise MachineProfileError(
            "Complete PBS machine profile required for scientific case; "
            "missing paths: " + ", ".join(missing)
        )
    # The existing installed v2 manifest, not the machine profile, determines
    # which stack module/site setup to load inside the scientific PBS script.
    from .site import runtime_contract_context
    install = profile.paths["installation_root"]
    stack = profile.paths["stack_root"]
    contract = runtime_contract_context(install, stack)
    setup = Path(contract["stack_site_setup"])
    if not setup.is_absolute():
        setup = stack / setup
    declared_setup = Path(str(profile.environment["setup"]))
    if declared_setup.resolve() != setup.resolve():
        raise MachineProfileError(
            "environment.setup differs from the installed MONAN-JEDI "
            f"runtime v2 contract: configured {declared_setup}, installed {setup}"
        )
    module_root = Path(contract["stack_module_root"])
    if not module_root.is_absolute():
        module_root = stack / module_root
    if not setup.is_file() or not module_root.is_dir():
        raise MachineProfileError(
            f"Scientific stack runtime is incomplete: setup={setup}, modules={module_root}"
        )

    return {
        "site": {"name": profile.name},
        "stack": {"load": True, "root": str(stack)},
        "jedi": {"install_root": str(install)},
        "environment": {
            env_name: str(profile.paths[path_name])
            for path_name, env_name in _PBS_LEGACY_PATHS.items()
            if path_name not in {"installation_root", "stack_root"}
        },
        "runtime": {"unload_anaconda": True, "validate_python": False},
    }
