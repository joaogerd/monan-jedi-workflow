"""MPAS forecast stage contracts."""

from pathlib import Path

from ....core.stage import RunContext, Stage, StageResult
from ....core.validation import ValidationReport
from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .output_validation import MpasOutputContract, validate_output_contract
from .products import MpasForecastProduct
from .staging import LinkSpec, TemplateSpec, render_template, stage_link


class MpasForecastStage(Stage):
    """Execute or validate one MPAS forecast through an explicit backend."""

    def __init__(self, product: MpasForecastProduct, run_dir: Path, contract: MpasOutputContract, *, request: ExecutionRequest | None = None, backend: ExecutionBackend | None = None, links: tuple[LinkSpec, ...] = (), templates: tuple[TemplateSpec, ...] = ()) -> None:
        if (request is None) != (backend is None):
            raise ValueError("MPAS request and backend must be provided together.")
        if request is not None and request.cwd != run_dir:
            raise ValueError("MPAS request cwd must match run_dir.")
        self.product, self.run_dir, self.contract = product, run_dir, contract
        self.request, self.backend, self.links, self.templates = request, backend, links, templates
        token = product.init_time.replace("-", "").replace("_", "").replace(":", "")
        self._spec = StageSpec(f"mpas_forecast_{token}_f{product.lead_hours:03d}", "model.mpas.forecast")

    @property
    def spec(self) -> StageSpec:
        """Return the unique scheduler-neutral stage declaration."""
        return self._spec

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Validate declared staging sources."""
        report = ValidationReport(subject=f"stage:{self.spec.name}:inputs")
        for item in self.links:
            if not item.source.exists():
                report.add("mpas.link_source", f"MPAS link source is missing: {item.source}")
        for item in self.templates:
            if not item.source.is_file():
                report.add("mpas.template_source", f"MPAS template is missing: {item.source}")
        return report

    def prepare(self, context: RunContext) -> StageResult:
        """Create the run directory and stage declared inputs."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        values = {"workspace": str(context.workspace), "run_dir": str(self.run_dir), "init_time": self.product.init_time, "valid_time": self.product.valid_time, "lead_hours": self.product.lead_hours, "restart": str(self.product.restart), "state": str(self.product.state)}
        for item in self.links:
            stage_link(item)
        for item in self.templates:
            render_template(item, values)
        return StageResult(f"Prepared MPAS forecast: {self.run_dir}.")

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
