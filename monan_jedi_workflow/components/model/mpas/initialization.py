"""MPAS initialization products and executable stage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Formatter
from typing import Mapping

from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .execution_stage import MpasExecutionStage
from .output_validation import MpasOutputContract
from .products import MPAS_TIME_FORMAT, MpasProductLayoutError, normalize_mpas_time
from .staging import LinkSpec, TemplateSpec


def mpas_initialization_context(cycle_time: str) -> dict[str, str | int]:
    """Build canonical template values for one MPAS initialization.

    Parameters
    ----------
    cycle_time : str
        Initialization time in MPAS or timezone-aware ISO-8601 form.

    Returns
    -------
    dict[str, str | int]
        Time and zero-lead values shared by initialization templates.
    """
    normalized = normalize_mpas_time(cycle_time)
    cycle = datetime.strptime(normalized, MPAS_TIME_FORMAT)
    return {
        "cycle_time": normalized,
        "init_time": normalized,
        "valid_time": normalized,
        "init_yyyymmddhh": cycle.strftime("%Y%m%d%H"),
        "valid_yyyymmddhh": cycle.strftime("%Y%m%d%H"),
        "mpas_valid_file_time": cycle.strftime("%Y-%m-%d_%H.%M.%S"),
        "lead_hours": 0,
        "lead_hours_03d": "000",
    }


@dataclass(frozen=True)
class MpasInitializationProduct:
    """Describe the state created for one MPAS initialization time."""

    cycle_time: str
    state: Path

    def __post_init__(self) -> None:
        """Normalize the cycle time through the shared MPAS time contract."""
        try:
            object.__setattr__(self, "cycle_time", normalize_mpas_time(self.cycle_time))
        except MpasProductLayoutError as exc:
            raise ValueError(str(exc)) from exc


@dataclass(frozen=True)
class MpasInitializationProductLayout:
    """Resolve initial MPAS state files from an explicit path template."""

    root: Path
    state_template: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "MpasInitializationProductLayout":
        """Build a layout from `model.mpas.initialization_products` settings."""
        try:
            root = values["root"]
            state = values["state_template"]
        except KeyError as exc:
            raise MpasProductLayoutError(f"model.mpas.initialization_products missing {exc.args[0]}.") from exc
        if not isinstance(root, str) or not root or not isinstance(state, str) or not state:
            raise MpasProductLayoutError("MPAS initialization product settings must be non-empty strings.")
        return cls(Path(root), state)

    def __post_init__(self) -> None:
        """Reject implicit roots and undocumented state-template placeholders."""
        if not self.root.is_absolute():
            raise MpasProductLayoutError("MPAS initialization_products.root must be an absolute path.")
        allowed = set(mpas_initialization_context("2000-01-01_00:00:00"))
        names = {name for _, name, _, _ in Formatter().parse(self.state_template) if name}
        unknown = names.difference(allowed)
        if unknown:
            raise MpasProductLayoutError(
                f"unsupported field(s) in MPAS initialization path template: {', '.join(sorted(unknown))}."
            )

    def initialize(self, cycle_time: str) -> MpasInitializationProduct:
        """Resolve the initial MPAS state artifact for one cycle time."""
        values = mpas_initialization_context(cycle_time)
        path = Path(self.state_template.format_map(values))
        return MpasInitializationProduct(str(values["cycle_time"]), path if path.is_absolute() else self.root / path)


class MpasInitializationStage(MpasExecutionStage):
    """Execute MPAS initialization and publish one initial state artifact."""

    def __init__(
        self,
        product: MpasInitializationProduct,
        run_dir: Path,
        contract: MpasOutputContract,
        *,
        request: ExecutionRequest | None = None,
        backend: ExecutionBackend | None = None,
        links: tuple[LinkSpec, ...] = (),
        templates: tuple[TemplateSpec, ...] = (),
    ) -> None:
        self.product = product
        token = product.cycle_time.replace("-", "").replace("_", "").replace(":", "")
        spec = StageSpec(
            name=f"mpas_init_{token}",
            command="model.mpas.initialize",
            description="Execute MPAS initialization and validate the initial state.",
        )
        files = (product.state, *contract.required_files)
        values = {**mpas_initialization_context(product.cycle_time), "state": str(product.state)}
        super().__init__(
            spec,
            run_dir,
            MpasOutputContract(files, contract.log_path, contract.required_log_markers),
            request=request,
            backend=backend,
            links=links,
            templates=templates,
            values=values,
            artifacts=(product.state,),
        )
