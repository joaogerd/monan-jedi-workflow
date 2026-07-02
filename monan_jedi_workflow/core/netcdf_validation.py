"""Structural NetCDF validation for producer-consumer artifact contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .netcdf import NetcdfFormat, detect_netcdf_format
from .validation import ValidationReport


@dataclass(frozen=True)
class NetcdfStructureContract:
    """Declare structural expectations for one NetCDF artifact.

    Parameters
    ----------
    consumer : str
        Consumer stage or executable using the artifact.
    accepted_formats : tuple[NetcdfFormat, ...], default=()
        Accepted container formats. An empty tuple disables format checking.
    required_variables : tuple[str, ...], default=()
        Variable names that must exist.
    required_dimensions : Mapping[str, int | None], default={}
        Dimensions that must exist. A positive value requires the exact length;
        ``None`` requires existence only.
    required_global_attributes : Mapping[str, str | None], default={}
        Global attributes that must exist. A string value also requires an exact
        string representation match.
    time_variable : str | None, default=None
        Optional variable containing character or CF-style time values.
    expected_time : str | None, default=None
        Time that must be present in `time_variable` when configured.
    """

    consumer: str
    accepted_formats: tuple[NetcdfFormat, ...] = ()
    required_variables: tuple[str, ...] = ()
    required_dimensions: Mapping[str, int | None] = field(default_factory=dict)
    required_global_attributes: Mapping[str, str | None] = field(default_factory=dict)
    time_variable: str | None = None
    expected_time: str | None = None


def _time_strings(variable: Any) -> tuple[str, ...]:
    """Decode character or numeric NetCDF time values to comparable strings."""
    import numpy as np

    values = variable[:]
    if getattr(variable, "units", None):
        from netCDF4 import num2date

        decoded = num2date(values, units=variable.units, calendar=getattr(variable, "calendar", "standard"))
        return tuple(str(item) for item in np.asarray(decoded).reshape(-1))
    if getattr(values, "dtype", None) is not None and values.dtype.kind in {"S", "U"}:
        from netCDF4 import chartostring

        if values.ndim > 1:
            values = chartostring(values)
        return tuple(str(item.decode() if isinstance(item, bytes) else item).strip("\x00 ") for item in np.asarray(values).reshape(-1))
    return tuple(str(item) for item in np.asarray(values).reshape(-1))


def validate_netcdf_structure(path: Path, contract: NetcdfStructureContract) -> ValidationReport:
    """Validate physical format and structural content of one NetCDF file.

    Parameters
    ----------
    path : Path
        NetCDF artifact to inspect.
    contract : NetcdfStructureContract
        Producer-consumer structural contract.

    Returns
    -------
    ValidationReport
        Complete report of detected format, schema, metadata, and time issues.

    Notes
    -----
    The validator reports all observable contract violations rather than failing
    on the first one. This makes a failed preflight check actionable before a
    long MPI or PBS submission.
    """
    report = ValidationReport(subject=f"netcdf:{contract.consumer}:{path}")
    if not path.is_file() or path.stat().st_size == 0:
        report.add("netcdf.missing", f"NetCDF file is missing or empty: {path}", path=str(path))
        return report

    observed = detect_netcdf_format(path)
    if contract.accepted_formats and observed not in contract.accepted_formats:
        allowed = ", ".join(item.value for item in contract.accepted_formats)
        report.add(
            "netcdf.format",
            f"{contract.consumer} does not accept {observed.value} for {path}; accepted formats: {allowed}.",
            path=str(path),
        )

    try:
        from netCDF4 import Dataset
    except ImportError:
        report.add(
            "netcdf.library",
            "netCDF4 Python bindings are required for structural NetCDF validation.",
            path=str(path),
        )
        return report

    try:
        with Dataset(path, "r") as dataset:
            variables = set(dataset.variables)
            for name in contract.required_variables:
                if name not in variables:
                    report.add("netcdf.variable", f"Required NetCDF variable is missing: {name}", path=str(path))

            for name, expected_size in contract.required_dimensions.items():
                if name not in dataset.dimensions:
                    report.add("netcdf.dimension", f"Required NetCDF dimension is missing: {name}", path=str(path))
                    continue
                if expected_size is not None and len(dataset.dimensions[name]) != expected_size:
                    report.add(
                        "netcdf.dimension_size",
                        f"NetCDF dimension {name} has size {len(dataset.dimensions[name])}; expected {expected_size}.",
                        path=str(path),
                    )

            attributes = set(dataset.ncattrs())
            for name, expected_value in contract.required_global_attributes.items():
                if name not in attributes:
                    report.add("netcdf.attribute", f"Required NetCDF global attribute is missing: {name}", path=str(path))
                    continue
                if expected_value is not None and str(dataset.getncattr(name)) != expected_value:
                    report.add(
                        "netcdf.attribute_value",
                        f"NetCDF global attribute {name} is {dataset.getncattr(name)!r}; expected {expected_value!r}.",
                        path=str(path),
                    )

            if contract.time_variable is not None:
                if contract.time_variable not in variables:
                    report.add(
                        "netcdf.time_variable",
                        f"Required NetCDF time variable is missing: {contract.time_variable}",
                        path=str(path),
                    )
                elif contract.expected_time is not None:
                    values = _time_strings(dataset.variables[contract.time_variable])
                    if contract.expected_time not in values:
                        report.add(
                            "netcdf.time_value",
                            f"NetCDF time variable {contract.time_variable} does not contain {contract.expected_time}.",
                            path=str(path),
                        )
    except OSError as exc:
        report.add("netcdf.open", f"Cannot open NetCDF file {path}: {exc}", path=str(path))
    return report
