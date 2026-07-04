"""Regression tests for restart-safe local workflow execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from monan_jedi_workflow.core.stage import RunContext, Stage, StageResult
from monan_jedi_workflow.core.state import RunState, StageStatus
from monan_jedi_workflow.core.validation import ValidationReport
from monan_jedi_workflow.core.workflow_spec import StageSpec, WorkflowSpec
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner


class FileStage(Stage):
    """Publish one deterministic file for runner lifecycle regression tests."""

    def __init__(self, spec: StageSpec, output: Path) -> None:
        self._spec = spec
        self.output = output
        self.calls = 0

    @property
    def spec(self) -> StageSpec:
        """Return the test stage declaration."""
        return self._spec

    def run(self, context: RunContext) -> StageResult:
        """Write the declared output and record one execution."""
        self.calls += 1
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(self.spec.name, encoding="utf-8")
        return StageResult(message=f"Ran {self.spec.name}.", artifacts=(self.output,))

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Require the declared file to exist."""
        report = ValidationReport(subject=self.spec.name)
        if not self.output.is_file():
            report.add("test.output_missing", f"Missing output: {self.output}")
        return report


def _context(tmp_path: Path) -> RunContext:
    """Build an isolated runner context."""
    return RunContext("test", "local-runner", tmp_path / "workspace", config={})


def test_local_runner_retries_interrupted_running_state(tmp_path: Path) -> None:
    """An inherited running state must become retryable rather than invalid."""
    context = _context(tmp_path)
    stage = FileStage(StageSpec("single", "test.single"), tmp_path / "single.done")
    runner = LocalWorkflowRunner(WorkflowSpec.from_stages("test", [stage.spec]), {stage.spec.name: stage})
    state = RunState("test", "local-runner")
    state.stage("single").transition(StageStatus.PREPARED, message="prepared")
    state.stage("single").transition(StageStatus.RUNNING, message="interrupted")
    state.save(context.state_path)

    assert len(runner.run(context)) == 1
    assert stage.calls == 1
    assert stage.output.is_file()


def test_local_runner_force_reexecutes_successful_stage(tmp_path: Path) -> None:
    """Force must move succeeded state back through a legal lifecycle path."""
    context = _context(tmp_path)
    stage = FileStage(StageSpec("single", "test.single"), tmp_path / "single.done")
    runner = LocalWorkflowRunner(WorkflowSpec.from_stages("test", [stage.spec]), {stage.spec.name: stage})

    assert len(runner.run(context)) == 1
    assert runner.run(context) == ()
    assert len(runner.run(context, force=True)) == 1
    assert stage.calls == 2


def test_local_runner_revalidates_declared_dependencies(tmp_path: Path) -> None:
    """A downstream local stage must reject a missing upstream artifact."""
    context = _context(tmp_path)
    first = FileStage(StageSpec("first", "test.first"), tmp_path / "first.done")
    second = FileStage(StageSpec("second", "test.second", needs=("first",)), tmp_path / "second.done")
    runner = LocalWorkflowRunner(
        WorkflowSpec.from_stages("test", [first.spec, second.spec]),
        {"first": first, "second": second},
    )
    runner.run(context)
    first.output.unlink()

    assert len(runner.run(context)) == 2
    assert first.output.is_file() and second.output.is_file()
