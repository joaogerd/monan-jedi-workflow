"""WPS intermediate product identity and path resolution."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Formatter
from typing import Mapping

from ..mpas.products import MPAS_TIME_FORMAT, normalize_mpas_time


class WpsProductError(ValueError):
    """Raised when WPS product settings are invalid."""


@dataclass(frozen=True)
class WpsIntermediateProduct:
    """One `ungrib` FILE artifact consumed by MPAS initialization."""

    init_time: str
    intermediate: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "init_time", normalize_mpas_time(self.init_time))

    @property
    def wps_time(self) -> str:
        """Return the timestamp used after the WPS FILE prefix."""
        return datetime.strptime(self.init_time, MPAS_TIME_FORMAT).strftime("%Y-%m-%d_%H")


@dataclass(frozen=True)
class WpsIntermediateProductLayout:
    """Resolve declared WPS intermediate products from explicit templates."""

    root: Path
    intermediate_template: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "WpsIntermediateProductLayout":
        root, template = values.get("root"), values.get("intermediate_template")
        if not isinstance(root, str) or not root or not isinstance(template, str) or not template:
            raise WpsProductError("WPS product root and intermediate_template must be non-empty strings.")
        return cls(Path(root), template)

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise WpsProductError("WPS ungrib_products.root must be an absolute path.")
        fields = {name for _, name, _, _ in Formatter().parse(self.intermediate_template) if name}
        unknown = fields.difference({"init_time", "init_yyyymmddhh", "wps_time"})
        if unknown:
            raise WpsProductError(f"Unsupported WPS path token(s): {', '.join(sorted(unknown))}.")

    def product(self, init_time: str) -> WpsIntermediateProduct:
        """Resolve one WPS FILE product for an initialization time."""
        normalized = normalize_mpas_time(init_time)
        timestamp = datetime.strptime(normalized, MPAS_TIME_FORMAT)
        values = {
            "init_time": normalized,
            "init_yyyymmddhh": timestamp.strftime("%Y%m%d%H"),
            "wps_time": timestamp.strftime("%Y-%m-%d_%H"),
        }
        path = Path(self.intermediate_template.format_map(values))
        return WpsIntermediateProduct(normalized, path if path.is_absolute() else self.root / path)
