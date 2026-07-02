"""Reusable MPAS execution stage base."""

from collections.abc import Mapping
from pathlib import Path

from ....core.stage import RunContext, Stage, StageResult
from ....core.validation import ValidationReport
from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .output_validation import MpasOutputContract, validate_output_contract
from .staging import LinkSpec, TemplateSpec, render_template, stage_link


class MpasExecutionStage(Stage):
    """Base class for MPAS commands with explicit staging and execution contracts.

    Parameters
    ----------
    spec : StageSpec
        Unique scheduler-neutral stage declaration.
    run_dir : Path
        Command working directory.
    contract : MpasOutputContract
        Required outputs and optional log markers.
    request : ExecutionRequest | None, default=None
        Explicit command request.
    backend : ExecutionBackend | None, default=None
        Selected local or platform execution backend.
    links : tuple[LinkSpec, ...], default=()
        Idempotent symbolic links staged before execution.
    templates : tuple[TemplateSpec, ...], default=()
        Templates rendered before execution.
    values : Mapping[str, object] | None, default=None
        Explicit template context excluding workspace and run directory.
    artifacts : tuple[Path, ...], default=()
        Published artifacts after output validation.
    """

    def __init__(
        self,
        spec: StageSpec,
        run_dir: Path,
        contract: MpasOutputContract,
        *,
        request: ExecutionRequest | None = None,
        backend: ExecutionBackend | None = None,
        links: tuple[LinkSpec, ...] = (),
        templates: tuple[TemplateSpec, ...] = (),
        values: Mapping[str, object] | None = None,
        artifacts: tuple[Path, ...] = (),
    ) -> None:
        if (request is None) != (backend is None):
            raise ValueError("MPAS request and backend must be provided together.")
        if request is not None and request.cwd != run_dir:
            raise ValueError("MPAS request cwd must match run_dir.")
        self._spec = spec
        self.run_dir = run_dir
        self.contract = contract
        self.request = request
        self.backend = backend
        self.links = links
        self.templates = templates
        self.values = dict(values or {})
        self.artifacts = artifacts

    @property
    def spec(self) -> StageSpec:
        """Return the scheduler-neutral stage declaration."""
        return self._spec

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Validate declared link and template sources."""
        report = ValidationReport(subject=f"stage:{self.spec.name}:inputs")
        for item in self.links:
            if not item.source.exists():
                report.add("mpas.link_source", f"MPAS link source is missing: {item.source}", path=str(item.source))
        for item in self.templates:
            if not item.source.is_file():
                report.add("mpas.template_source", f"MPAS template is missing: {item.source}", path=str(item.source))
        return report

    def prepare(self, context: RunContext) -> StageResult:
        """Create the run directory and stage declared inputs."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        values = {"workspace": str(context.workspace), "run_dir": str(self.run_dir), **self.values}
        for item in self.links:
            stage_link(item)
        for item in self.templates:
            render_template(item, values)
        return StageResult(message=f"Prepared MPAS stage: {self.spec.name}.")

    def run(self, context: RunContext) -> StageResult:
        """Submit and wait through the selected execution backend."""
        if self.request is None or self.backend is None:
            raise RuntimeError("MPAS execution requires an explicit request and backend.")
        handle = self.backend.submit(self.request)
        self.backend.wait(handle)
        return StageResult(message=f"MPAS execution completed: {handle.identifier}.")

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate the declared output contract."""
        return validate_output_contract(self.run_dir, self.contract)

    def finalize(self, context: RunContext) -> StageResult:
        """Publish declared artifacts after output validation."""
        return StageResult(message=f"Finalized MPAS stage: {self.spec.name}.", artifacts=self.artifacts)
