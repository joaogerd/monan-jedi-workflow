"""MPAS initialization component."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .execution_stage import MpasExecutionStage
from .output_validation import MpasOutputContract
from .products import MpasProductLayoutError, normalize_mpas_time
from .staging import LinkSpec, TemplateSpec


@dataclass(frozen=True)
class MpasInitializationProduct:
    """Describe the state created for one MPAS initialization time.

    Parameters
    ----------
    cycle_time : str
        Analysis or initialization time in MPAS or timezone-aware ISO-8601 form.
    state : Path
        Initial MPAS state artifact produced by the initialization command.
    """

    cycle_time: str
    state: Path

    def __post_init__(self) -> None:
        """Normalize the cycle time through the shared MPAS time contract."""
        try:
            object.__setattr__(self, "cycle_time", normalize_mpas_time(self.cycle_time))
        except MpasProductLayoutError as exc:
            raise ValueError(str(exc)) from exc


class MpasInitializationStage(MpasExecutionStage):
    """Execute MPAS initialization and publish one initial state artifact.

    Parameters
    ----------
    product : MpasInitializationProduct
        Initialization identity and expected state artifact.
    run_dir : Path
        Initialization working directory.
    contract : MpasOutputContract
        Additional output and log validation requirements.
    request : ExecutionRequest | None, default=None
        Explicit command request.
    backend : ExecutionBackend | None, default=None
        Selected execution backend.
    links : tuple[LinkSpec, ...], default=()
        Links staged before initialization.
    templates : tuple[TemplateSpec, ...], default=()
        Templates rendered before initialization.
    """

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
        values = {
            "cycle_time": product.cycle_time,
            "init_time": product.cycle_time,
            "valid_time": product.cycle_time,
            "init_yyyymmddhh": product.cycle_time.replace("-", "").replace("_", "")[:10],
            "valid_yyyymmddhh": product.cycle_time.replace("-", "").replace("_", "")[:10],
            "mpas_valid_file_time": product.cycle_time.replace(":", "."),
            "lead_hours": 0,
            "lead_hours_03d": "000",
            "state": str(product.state),
        }
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
