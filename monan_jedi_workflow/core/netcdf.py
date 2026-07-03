"""NetCDF format detection and consumer-facing compatibility policies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .validation import ValidationReport


class NetcdfFormat(str, Enum):
    """Recognized NetCDF container formats."""

    CLASSIC = "netcdf3-classic"
    OFFSET_64BIT = "netcdf3-64bit-offset"
    CDF5 = "netcdf5"
    NETCDF4 = "netcdf4-hdf5"
    UNKNOWN = "unknown"


_MAGIC = {
    b"CDF\x01": NetcdfFormat.CLASSIC,
    b"CDF\x02": NetcdfFormat.OFFSET_64BIT,
    b"CDF\x05": NetcdfFormat.CDF5,
    b"\x89HDF\r\n\x1a\n": NetcdfFormat.NETCDF4,
}


def detect_netcdf_format(path: Path) -> NetcdfFormat:
    """Detect the physical container format from a NetCDF file signature.

    Parameters
    ----------
    path : Path
        Candidate NetCDF file.

    Returns
    -------
    NetcdfFormat
        Detected container format, or ``UNKNOWN`` when no known signature is
        present.
    """
    header = path.read_bytes()[:8]
    for magic, format_name in _MAGIC.items():
        if header.startswith(magic):
            return format_name
    return NetcdfFormat.UNKNOWN


@dataclass(frozen=True)
class NetcdfPolicy:
    """Declare formats accepted by one artifact consumer.

    Parameters
    ----------
    consumer : str
        Consumer stage or executable name.
    accepted_formats : tuple[NetcdfFormat, ...]
        Formats known to be readable by the consumer build.
    """

    consumer: str
    accepted_formats: tuple[NetcdfFormat, ...]

    def validate(self, path: Path) -> ValidationReport:
        """Validate one file against the consumer format policy.

        Parameters
        ----------
        path : Path
            NetCDF file to inspect.

        Returns
        -------
        ValidationReport
            Valid report when the detected container format is accepted.
        """
        report = ValidationReport(subject=f"netcdf:{path}")
        if not path.is_file():
            report.add("netcdf.missing", f"NetCDF file is missing: {path}", path=str(path))
            return report
        observed = detect_netcdf_format(path)
        if observed not in self.accepted_formats:
            allowed = ", ".join(item.value for item in self.accepted_formats)
            report.add(
                "netcdf.format",
                f"{self.consumer} does not accept {observed.value} for {path}; accepted formats: {allowed}.",
                path=str(path),
            )
        return report
