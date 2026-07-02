"""Build JACI PBS backends from resolved site configuration."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .base import ExecutionBackend
from .jaci_backend import JaciPbsBackend
from .jaci_pbs import JaciPbsResources


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
    """Validate shell prelude lines as explicit English-free configuration text."""
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise JaciConfigurationError(f"{label} must be a list of non-empty strings.")
    return tuple(value)


def jaci_backend_factory(
    config: Mapping[str, object],
    *,
    stage_kind: str,
) -> Callable[[str], ExecutionBackend]:
    """Create a backend factory for one configured JACI stage kind.

    Parameters
    ----------
    config : Mapping[str, object]
        Fully resolved case and site configuration.
    stage_kind : str
        JACI PBS profile key, such as ``initialization`` or ``forecast``.

    Returns
    -------
    Callable[[str], ExecutionBackend]
        Factory receiving a unique stage name and returning a configured PBS
        backend for that stage.

    Notes
    -----
    The factory creates a distinct backend per stage so the scheduler-visible
    job name and rendered PBS script remain deterministic and collision-free.
    """
    platform = _mapping(config.get("platform"), "platform")
    jaci = _mapping(platform.get("jaci"), "platform.jaci")
    pbs = _mapping(jaci.get("pbs"), "platform.jaci.pbs")
    common = _mapping(pbs.get("common", {}), "platform.jaci.pbs.common")
    profile = _mapping(pbs.get(stage_kind), f"platform.jaci.pbs.{stage_kind}")
    label = f"platform.jaci.pbs.{stage_kind}"
    queue = _string(profile, "queue", label)
    walltime = _string(profile, "walltime", label)
    select = _integer(profile, "select", label, default=1)
    ncpus = _integer(profile, "ncpus", label)
    mpiprocs = _integer(profile, "mpiprocs", label)
    prelude = (*_lines(common.get("prelude"), "platform.jaci.pbs.common.prelude"), *_lines(profile.get("prelude"), f"{label}.prelude"))
    qsub = _string(common, "qsub", "platform.jaci.pbs.common", default="qsub")
    qstat = _string(common, "qstat", "platform.jaci.pbs.common", default="qstat")
    poll_seconds = _integer(common, "poll_seconds", "platform.jaci.pbs.common", default=30)
    timeout = common.get("timeout_seconds")
    if timeout is not None and (not isinstance(timeout, int) or timeout < 1):
        raise JaciConfigurationError("platform.jaci.pbs.common.timeout_seconds must be a positive integer when set.")

    def create(stage_name: str) -> ExecutionBackend:
        """Create one backend using the stage name as the PBS job name."""
        return JaciPbsBackend(
            JaciPbsResources(queue, walltime, select, ncpus, mpiprocs, stage_name),
            prelude=prelude,
            qsub=qsub,
            qstat=qstat,
            poll_seconds=poll_seconds,
            timeout_seconds=timeout,
        )

    return create
