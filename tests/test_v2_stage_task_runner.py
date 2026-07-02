"""Tests for V2 isolated stage orchestration tasks."""

from __future__ import annotations

from pathlib import Path

import pytest

from monan_jedi_workflow.core.stage import RunContext, Stage, StageResult
from monan_jedi_workflow.core.validation import ValidationError, ValidationReport
from monan_jedi_workflow.core.workflow_spec import StageSpec, WorkflowSpec
from monan_jedi_workflow.orchestration.local import StageTaskRunner


class FileStage(Stage):
    """Small stage that publishes one file for task-runner testing."""

    def __init__(self, spec: StageSpec, output: Path) -> None:
        self._spec = spec
        self.output = output

    @property
    def spec(self) -> StageSpec:
        """Return the test stage declaration."""
        return self._spec

    def run(self, context: RunContext) -> StageResult:
        """Publish the deterministic test output."""
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(self.spec.name, encoding="utf-8")
        return StageResult(message=f"Ran {self.spec.name}.", artifacts=(self.output,))

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Require the deterministic published file."""
        report = ValidationReport(subject=self.spec.name)
        if not self.output.is_file():
            report.add("test.output_missing", f"Missing output: {self.output}")
        return report


def test_task_runner_requires_valid_dependency_outputs(tmp_path: Path) -> None:
    """A downstream orchestration task cannot bypass dependency artifacts."""
    first = FileStage(StageSpec("first", "test.first"), tmp_path / "first.done")
    second = FileStage(StageSpec("second", "test.second", needs=("first",)), tmp_path / "second.done")
    spec = WorkflowSpec.from_stages("test", (first.spec, second.spec))
    runner = StageTaskRunner(spec, {"first": first, "second": second})
    context = RunContext("test", "task", tmp_path / "workspace", config={})

    with pytest.raises(ValidationError, match="Missing output"):
        runner.run(context, "second")

    assert runner.run(context, "first") is not None
    assert runner.run(context, "second") is not None
    assert runner.run(context, "second") is None


def test_task_runner_retries_unknown_running_state(tmp_path: Path) -> None:
    """An inherited running state must become retryable instead of blocking tasks."""
    stage = FileStage(StageSpec("single", "test.single"), tmp_path / "single.done")
    spec = WorkflowSpec.from_stages("test", (stage.spec,))
    runner = StageTaskRunner(spec, {"single": stage})
    context = RunContext("test", "task", tmp_path / "workspace", config={})
    state = context.state_path
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        '{"workflow":"test","case":"task","stages":{"single":{"name":"single","status":"running","updated_at":"2026-07-02T00:00:00Z","message":"old"}}}',
        encoding="utf-8",
    )

    assert runner.run(context, "single") is not None
    assert stage.output.is_file()
