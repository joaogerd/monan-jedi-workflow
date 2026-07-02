"""MPAS forecast stage contracts."""

from pathlib import Path

from ....core.stage import RunContext, Stage, StageResult
from ....core.validation import ValidationReport
from ....core.workflow_spec import StageSpec
from .output_validation import MpasOutputContract, validate_output_contract
from .products import MpasForecastProduct


class MpasForecastStage(Stage):
    """Validate products of one externally executed MPAS forecast."""

    def __init__(self, product: MpasForecastProduct, run_dir: Path, contract: MpasOutputContract) -> None:
        self.product = product
        self.run_dir = run_dir
        self.contract = contract
        self._spec = StageSpec("mpas_forecast", "model.mpas.forecast")

    @property
    def spec(self) -> StageSpec:
        """Return the stage declaration."""
        return self._spec

    def run(self, context: RunContext) -> StageResult:
        """Reject direct local execution until a backend is selected."""
        raise RuntimeError("MPAS forecast execution requires a selected platform backend.")

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate restart, state, and configured output products."""
        files = (self.product.restart, self.product.state, *self.contract.required_files)
        return validate_output_contract(self.run_dir, MpasOutputContract(files, self.contract.log_path, self.contract.required_log_markers))
