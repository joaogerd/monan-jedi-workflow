"""MPAS forecast specialization of the reusable execution stage."""

from collections.abc import Mapping
from pathlib import Path

from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .execution_stage import MpasExecutionStage
from .output_validation import MpasOutputContract
from .products import MpasForecastProduct
from .staging import LinkSpec, TemplateSpec


class MpasForecastStage(MpasExecutionStage):
    """Execute one MPAS forecast and publish restart and state products.

    Parameters
    ----------
    product : MpasForecastProduct
        Forecast identity and expected restart/state artifacts.
    run_dir : Path
        Forecast working directory.
    contract : MpasOutputContract
        Additional output and log validation requirements.
    request : ExecutionRequest | None, default=None
        Explicit command request.
    backend : ExecutionBackend | None, default=None
        Selected execution backend.
    links : tuple[LinkSpec, ...], default=()
        Links staged before the forecast.
    templates : tuple[TemplateSpec, ...], default=()
        Templates rendered before the forecast.
    extra_values : Mapping[str, object] | None, default=None
        Explicit upstream artifact values such as ``initial_state``. Core
        product tokens cannot be overridden.
    """

    def __init__(
        self,
        product: MpasForecastProduct,
        run_dir: Path,
        contract: MpasOutputContract,
        *,
        request: ExecutionRequest | None = None,
        backend: ExecutionBackend | None = None,
        links: tuple[LinkSpec, ...] = (),
        templates: tuple[TemplateSpec, ...] = (),
        extra_values: Mapping[str, object] | None = None,
    ) -> None:
        self.product = product
        token = product.init_time.replace("-", "").replace("_", "").replace(":", "")
        spec = StageSpec(
            name=f"mpas_forecast_{token}_f{product.lead_hours:03d}",
            command="model.mpas.forecast",
            description="Execute one MPAS forecast and validate restart/state products.",
        )
        files = (product.restart, product.state, *contract.required_files)
        values: dict[str, object] = {
            "init_time": product.init_time,
            "valid_time": product.valid_time,
            "init_yyyymmddhh": product.init_time.replace("-", "").replace("_", "")[:10],
            "valid_yyyymmddhh": product.valid_time.replace("-", "").replace("_", "")[:10],
            "mpas_valid_file_time": product.valid_time.replace(":", "."),
            "lead_hours": product.lead_hours,
            "lead_hours_03d": f"{product.lead_hours:03d}",
            "restart": str(product.restart),
            "state": str(product.state),
        }
        upstream = dict(extra_values or {})
        collision = set(values).intersection(upstream)
        if collision:
            raise ValueError(f"MPAS forecast extra values cannot override product tokens: {', '.join(sorted(collision))}.")
        values.update(upstream)
        super().__init__(
            spec,
            run_dir,
            MpasOutputContract(files, contract.log_path, contract.required_log_markers),
            request=request,
            backend=backend,
            links=links,
            templates=templates,
            values=values,
            artifacts=(product.restart, product.state),
        )
