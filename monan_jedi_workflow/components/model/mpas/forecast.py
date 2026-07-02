"""MPAS forecast stage contracts."""

from pathlib import Path

from ....core.stage import RunContext, Stage, StageResult
from ....core.validation import ValidationReport
from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .output_validation import MpasOutputContract, validate_output_contract
from .products import MpasForecastProduct


class MpasForecastStage(Stage):
    """Execute or validate one MPAS forecast through an explicit backend."""

    def __init__(self, product: MpasForecastProduct, run_dir: Path, contract: MpasOutputContract, *, request: ExecutionRequest | None = None, backend: ExecutionBackend | None = None) -> None:
        if (request is None) != (backend is None):
            raise ValueError("MPAS request and backend must be provided together.")
        if request is not None and request.cwd != run_dir:
            raise ValueError("MPAS request cwd must match run_dir.")
        self.product, self.run_dir, self.contract = product, run_dir, contract
        self.request, self.backend = request, backend
        token = product.init_time.replace("-", "").replace("_", "").replace(":", "")
        self._spec = StageSpec(f"mpas_forecast_{token}_f{product.lead_hours:03d}", "model.mpas.forecast")

    @property
    def spec(self) -> StageSpec:
        """Return the unique scheduler-neutral stage declaration."""
        return self._spec

    def run(self, context: RunContext) -> StageResult:
        """Submit and wait for the selected backend request."""
        if self.request is None or self.backend is None:
            raise RuntimeError("MPAS forecast execution requires an explicit request and backend.")
        handle = self.backend.submit(self.request)
        self.backend.wait(handle)
        return StageResult(f"MPAS execution completed: {handle.identifier}.")

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate restart, state, and configured output products."""
        files = (self.product.restart, self.product.state, *self.contract.required_files)
        return validate_output_contract(self.run_dir, MpasOutputContract(files, self.contract.log_path, self.contract.required_log_markers))
