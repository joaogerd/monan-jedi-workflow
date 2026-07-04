"""Compile MPAS artifact-validation settings into NetCDF checks."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ....core.netcdf import NetcdfFormat
from ....core.netcdf_validation import NetcdfStructureContract
from .output_validation import MpasNetcdfCheck


class MpasNetcdfContractError(ValueError):
    """Raised when `model.mpas.artifact_validation` is invalid."""


_FORMAT_NAMES = {
    "classic": NetcdfFormat.CLASSIC,
    "netcdf3-classic": NetcdfFormat.CLASSIC,
    "64bit-offset": NetcdfFormat.OFFSET_64BIT,
    "netcdf3-64bit-offset": NetcdfFormat.OFFSET_64BIT,
    "cdf5": NetcdfFormat.CDF5,
    "netcdf5": NetcdfFormat.CDF5,
    "netcdf4": NetcdfFormat.NETCDF4,
    "netcdf4-hdf5": NetcdfFormat.NETCDF4,
}


def _mapping(value: object, label: str) -> Mapping[str, object]:
    """Return one mapping or raise a contextual configuration error."""
    if not isinstance(value, Mapping):
        raise MpasNetcdfContractError(f"{label} must be a mapping.")
    return value


def _strings(value: object, label: str) -> tuple[str, ...]:
    """Read an optional list of non-empty strings."""
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise MpasNetcdfContractError(f"{label} must be a list of non-empty strings.")
    return tuple(value)


def _dimensions(value: object, label: str) -> dict[str, int | None]:
    """Read dimension presence or exact-size requirements."""
    if value is None:
        return {}
    mapping = _mapping(value, label)
    result: dict[str, int | None] = {}
    for name, size in mapping.items():
        if not isinstance(name, str) or not name:
            raise MpasNetcdfContractError(f"{label} keys must be non-empty strings.")
        if size is not None and (not isinstance(size, int) or size < 1):
            raise MpasNetcdfContractError(f"{label}.{name} must be a positive integer or null.")
        result[name] = size
    return result


def _attributes(value: object, label: str) -> dict[str, str | None]:
    """Read required global attributes and optional exact expected values."""
    if value is None:
        return {}
    mapping = _mapping(value, label)
    result: dict[str, str | None] = {}
    for name, expected in mapping.items():
        if not isinstance(name, str) or not name:
            raise MpasNetcdfContractError(f"{label} keys must be non-empty strings.")
        if expected is not None and not isinstance(expected, str):
            raise MpasNetcdfContractError(f"{label}.{name} must be a string or null.")
        result[name] = expected
    return result


def _formats(value: object, label: str) -> tuple[NetcdfFormat, ...]:
    """Read accepted NetCDF format aliases from YAML."""
    names = _strings(value, label)
    result: list[NetcdfFormat] = []
    for name in names:
        try:
            result.append(_FORMAT_NAMES[name.lower()])
        except KeyError as exc:
            supported = ", ".join(sorted(_FORMAT_NAMES))
            raise MpasNetcdfContractError(f"{label} contains unsupported format {name!r}; supported: {supported}.") from exc
    return tuple(result)


def artifact_check_from_mapping(
    value: object,
    *,
    path: Path,
    default_consumer: str,
    expected_time: str | None = None,
) -> MpasNetcdfCheck | None:
    """Compile one optional artifact validation declaration.

    Parameters
    ----------
    value : object
        Artifact validation mapping, or ``None`` to disable structural checking.
    path : Path
        Artifact path associated with the check.
    default_consumer : str
        Consumer name used when the mapping does not declare `consumer`.
    expected_time : str | None, default=None
        Forecast or initialization time available to a contract with
        `require_expected_time: true`.

    Returns
    -------
    MpasNetcdfCheck | None
        Compiled check, or ``None`` when no declaration exists.
    """
    if value is None:
        return None
    values = _mapping(value, "model.mpas.artifact_validation")
    consumer = values.get("consumer", default_consumer)
    if not isinstance(consumer, str) or not consumer:
        raise MpasNetcdfContractError("artifact_validation.consumer must be a non-empty string.")
    time_variable = values.get("time_variable")
    if time_variable is not None and (not isinstance(time_variable, str) or not time_variable):
        raise MpasNetcdfContractError("artifact_validation.time_variable must be a non-empty string when set.")
    require_expected = values.get("require_expected_time", False)
    if not isinstance(require_expected, bool):
        raise MpasNetcdfContractError("artifact_validation.require_expected_time must be boolean.")
    if require_expected and time_variable is None:
        raise MpasNetcdfContractError("artifact_validation.require_expected_time requires time_variable.")
    return MpasNetcdfCheck(
        path=path,
        contract=NetcdfStructureContract(
            consumer=consumer,
            accepted_formats=_formats(values.get("accepted_formats"), "artifact_validation.accepted_formats"),
            required_variables=_strings(values.get("required_variables"), "artifact_validation.required_variables"),
            required_dimensions=_dimensions(values.get("required_dimensions"), "artifact_validation.required_dimensions"),
            required_global_attributes=_attributes(values.get("required_global_attributes"), "artifact_validation.required_global_attributes"),
            time_variable=time_variable,
            expected_time=expected_time if require_expected else None,
        ),
    )


def mpas_artifact_check(
    config: Mapping[str, object],
    *,
    name: str,
    path: Path,
    default_consumer: str,
    expected_time: str | None = None,
) -> MpasNetcdfCheck | None:
    """Compile one named MPAS artifact check from resolved configuration.

    The optional declaration lives at:

    ``model.mpas.artifact_validation.<name>``.
    """
    model = _mapping(config.get("model"), "model")
    mpas = _mapping(model.get("mpas"), "model.mpas")
    validation = mpas.get("artifact_validation", {})
    values = _mapping(validation, "model.mpas.artifact_validation")
    return artifact_check_from_mapping(
        values.get(name),
        path=path,
        default_consumer=default_consumer,
        expected_time=expected_time,
    )
