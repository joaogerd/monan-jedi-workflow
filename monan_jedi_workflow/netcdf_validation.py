"""Structural NetCDF validation for scientific stage artifacts.

This module is intentionally independent of MPAS execution and PBS.  It turns a
small declarative contract into actionable validation errors so a stage can
distinguish "the file exists" from "the file is scientifically usable by the
next consumer".

The implementation was selectively recovered from the historical V2 work in
PR #48 and adapted to the current cycle-aware main branch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class NetcdfStructureContract:
    """Structural expectations for one NetCDF producer/consumer artifact."""

    consumer: str
    required_variables: tuple[str, ...] = ()
    required_dimensions: Mapping[str, int | None] = field(default_factory=dict)
    required_global_attributes: Mapping[str, str | None] = field(default_factory=dict)
    time_variable: str | None = None
    expected_time: str | None = None


def _time_strings(variable: Any) -> tuple[str, ...]:
    """Decode MPAS character timestamps or CF-style numeric times."""
    import numpy as np

    values = variable[:]
    dtype = getattr(values, "dtype", None)
    if dtype is not None and dtype.kind in {"S", "U"}:
        from netCDF4 import chartostring

        if values.ndim > 1:
            values = chartostring(values)
        return tuple(
            str(item.decode() if isinstance(item, bytes) else item).strip("\x00 ")
            for item in np.asarray(values).reshape(-1)
        )
    if getattr(variable, "units", None):
        from netCDF4 import num2date

        decoded = num2date(
            values,
            units=variable.units,
            calendar=getattr(variable, "calendar", "standard"),
        )
        return tuple(str(item) for item in np.asarray(decoded).reshape(-1))
    return tuple(str(item) for item in np.asarray(values).reshape(-1))


def validate_netcdf_structure(path: Path, contract: NetcdfStructureContract) -> list[str]:
    """Return all structural violations observed in one NetCDF artifact."""
    issues: list[str] = []
    if not path.is_file() or path.stat().st_size == 0:
        return [f"NetCDF file is missing or empty: {path}"]

    try:
        from netCDF4 import Dataset
    except ImportError:
        return ["netCDF4 Python bindings are required for structural NetCDF validation."]

    try:
        with Dataset(path, "r") as dataset:
            variables = set(dataset.variables)
            for name in contract.required_variables:
                if name not in variables:
                    issues.append(f"required variable is missing: {name}")

            for name, expected_size in contract.required_dimensions.items():
                if name not in dataset.dimensions:
                    issues.append(f"required dimension is missing: {name}")
                    continue
                observed = len(dataset.dimensions[name])
                if expected_size is not None and observed != expected_size:
                    issues.append(
                        f"dimension {name} has size {observed}; expected {expected_size}"
                    )

            attributes = set(dataset.ncattrs())
            for name, expected in contract.required_global_attributes.items():
                if name not in attributes:
                    issues.append(f"required global attribute is missing: {name}")
                    continue
                observed = str(dataset.getncattr(name))
                if expected is not None and observed != expected:
                    issues.append(
                        f"global attribute {name} is {observed!r}; expected {expected!r}"
                    )

            if contract.time_variable is not None:
                if contract.time_variable not in variables:
                    issues.append(
                        f"required time variable is missing: {contract.time_variable}"
                    )
                elif contract.expected_time is not None:
                    values = _time_strings(dataset.variables[contract.time_variable])
                    if contract.expected_time not in values:
                        issues.append(
                            f"time variable {contract.time_variable} does not contain "
                            f"{contract.expected_time}"
                        )
    except OSError as exc:
        issues.append(f"cannot open NetCDF file: {exc}")

    return [f"{contract.consumer}: {path}: {issue}" for issue in issues]
