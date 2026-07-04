"""Reusable MPAS execution stage base."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from ....core.stage import RunContext, Stage, StageResult
from ....core.validation import ValidationReport
from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .output_validation import MpasOutputContract, validate_output_contract
from .staging import LinkSpec, TemplateSpec, render_template, stage_link


class MpasExecutionStage(Stage):
    """Base class for MPAS commands with explicit staging and execution contracts."""

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

    def plan(self, context: RunContext) -> StageResult:
        """Plan work without launching scientific software."""
        if self.request is None or self.backend is None:
            return super().plan(context)
        resolver = getattr(self.backend, "resolve", None)
        if not callable(resolver):
            return StageResult(message=f"Plan {self.spec.name}.", artifacts=self.artifacts)
        resolved = resolver(self.request)
        payload = getattr(resolved, "to_dict", None)
        if not callable(payload):
            return StageResult(message=f"Plan {self.spec.name}.", artifacts=self.artifacts)
        record = context.workspace / ".monan-jedi-workflow" / "dry-run" / f"{self.spec.name}.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(payload(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        script = getattr(resolved, "script", None)
        artifacts = (*self.artifacts, record)
        if isinstance(script, Path):
            artifacts = (*artifacts, script)
        return StageResult(message=f"Resolved platform plan for {self.spec.name}.", artifacts=artifacts)

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Validate static inputs while deferring declared upstream products.

        Upstream artifacts are verified by their dependency stage during normal
        execution. Preparation-only preflight intentionally permits their output
        paths to be absent while it materializes a visible dangling link.
        """
        report = ValidationReport(subject=f"stage:{self.spec.name}:inputs")
        for item in self.links:
            if not item.source.exists() and not (context.prepare_only and item.upstream_artifact):
                report.add("mpas.link_source", f"MPAS link source is missing: {item.source}", path=str(item.source))
        for item in self.templates:
            if not item.source.is_file():
                report.add("mpas.template_source", f"MPAS template is missing: {item.source}", path=str(item.source))
        return report

    def prepare(self, context: RunContext) -> StageResult:
        """Create the run directory, links, and rendered templates.

        In preparation-only mode, only links marked as declared upstream
        artifacts may be dangling; all static sources remain mandatory.
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)
        values = {"workspace": str(context.workspace), "run_dir": str(self.run_dir), **self.values}
        for item in self.links:
            stage_link(item, allow_missing_source=context.prepare_only and item.upstream_artifact)
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
