"""Build JACI platform backends from resolved site configuration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from .base import ExecutionBackend
from .jaci.backend import JaciPlatformBackend
from .jaci.environment import JaciEnvironment
from .jaci.filesystem import JaciFilesystemPolicy
from .jaci.launcher import JaciMpiLauncher
from .jaci.scheduler import JaciSchedulerProfile


class JaciConfigurationError(ValueError):
    """Raised when `platform.jaci` configuration is invalid."""


def _mapping(value: object, label: str) -> Mapping[str, object]:
    """Return one required mapping with a contextual error."""
    if not isinstance(value, Mapping):
        raise JaciConfigurationError(f"{label} must be a mapping.")
    return value


def _string(values: Mapping[str, object], key: str, label: str, default: str | None = None) -> str:
    """Read one required or defaulted non-empty string."""
    value = values.get(key, default)
    if not isinstance(value, str) or not value:
        raise JaciConfigurationError(f"{label}.{key} must be a non-empty string.")
    return value


def _integer(values: Mapping[str, object], key: str, label: str, default: int | None = None) -> int:
    """Read one required or defaulted positive integer."""
    value = values.get(key, default)
    if not isinstance(value, int) or value < 1:
        raise JaciConfigurationError(f"{label}.{key} must be a positive integer.")
    return value


def _lines(value: object, label: str) -> tuple[str, ...]:
    """Read an optional list of explicit non-empty shell lines or argv items."""
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise JaciConfigurationError(f"{label} must be a list of non-empty strings.")
    return tuple(value)


def _variables(value: object, label: str) -> dict[str, str]:
    """Read optional platform environment variables."""
    if value is None:
        return {}
    values = _mapping(value, label)
    if not all(isinstance(name, str) and name and isinstance(item, str) for name, item in values.items()):
        raise JaciConfigurationError(f"{label} must map non-empty strings to strings.")
    return dict(values)


def _roots(value: object, label: str) -> tuple[Path, ...]:
    """Read optional absolute workspace roots enforced by the site policy."""
    return tuple(Path(item) for item in _lines(value, label))


def jaci_backend_factory(
    config: Mapping[str, object],
    *,
    stage_kind: str,
) -> Callable[[str], ExecutionBackend]:
    """Create one JACI backend factory for a scientific stage category.

    The stage supplies abstract resources in its own YAML. The site profile owns
    queue routing, node capacity, launcher syntax, environment, and filesystem
    policy. No MPAS configuration needs to name a scheduler command.
    """
    platform = _mapping(config.get("platform"), "platform")
    jaci = _mapping(platform.get("jaci"), "platform.jaci")
    scheduler = _mapping(jaci.get("scheduler"), "platform.jaci.scheduler")
    common = _mapping(scheduler.get("common", {}), "platform.jaci.scheduler.common")
    profile = _mapping(scheduler.get(stage_kind), f"platform.jaci.scheduler.{stage_kind}")
    profile_label = f"platform.jaci.scheduler.{stage_kind}"
    scheduler_profile = JaciSchedulerProfile(
        queue=_string(profile, "queue", profile_label),
        cores_per_node=_integer(profile, "cores_per_node", profile_label),
        max_mpi_ranks_per_node=_integer(profile, "max_mpi_ranks_per_node", profile_label),
    )

    launcher_values = _mapping(jaci.get("mpi_launcher"), "platform.jaci.mpi_launcher")
    launcher = JaciMpiLauncher(_lines(launcher_values.get("argv"), "platform.jaci.mpi_launcher.argv"))
    environment_values = _mapping(jaci.get("environment", {}), "platform.jaci.environment")
    environment = JaciEnvironment(
        prelude=_lines(environment_values.get("prelude"), "platform.jaci.environment.prelude"),
        variables=_variables(environment_values.get("variables"), "platform.jaci.environment.variables"),
    )
    filesystem_values = _mapping(jaci.get("filesystem", {}), "platform.jaci.filesystem")
    filesystem = JaciFilesystemPolicy(_roots(filesystem_values.get("allowed_workspace_roots"), "platform.jaci.filesystem.allowed_workspace_roots"))

    qsub = _string(common, "qsub", "platform.jaci.scheduler.common", default="qsub")
    qstat = _string(common, "qstat", "platform.jaci.scheduler.common", default="qstat")
    poll_seconds = _integer(common, "poll_seconds", "platform.jaci.scheduler.common", default=30)
    timeout = common.get("timeout_seconds")
    if timeout is not None and (not isinstance(timeout, int) or timeout < 1):
        raise JaciConfigurationError("platform.jaci.scheduler.common.timeout_seconds must be a positive integer when set.")

    def create(stage_name: str) -> ExecutionBackend:
        """Create a collision-free backend using the declared stage name."""
        return JaciPlatformBackend(
            scheduler=scheduler_profile,
            launcher=launcher,
            environment=environment,
            filesystem=filesystem,
            job_name=stage_name,
            qsub=qsub,
            qstat=qstat,
            poll_seconds=poll_seconds,
            timeout_seconds=timeout,
        )

    return create
