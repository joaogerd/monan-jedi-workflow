"""Tests for the V2 scheduler-neutral workflow foundation."""

from __future__ import annotations

from pathlib import Path

import pytest

from monan_jedi_workflow.core.netcdf import NetcdfFormat, NetcdfPolicy, detect_netcdf_format
from monan_jedi_workflow.core.stage import RunContext, Stage, StageResult
from monan_jedi_workflow.core.state import RunState, StageStatus
from monan_jedi_workflow.core.validation import ValidationReport
from monan_jedi_workflow.core.workflow_spec import StageSpec, WorkflowSpec, WorkflowSpecificationError
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner


class RecordingStage(Stage):
    """Small synchronous stage used to test the common lifecycle."""

    def __init__(self, spec: StageSpec, events: list[str]) -> None:
        self._spec = spec
        self.events = events

    @property
    def spec(self) -> StageSpec:
        """Return the declaration used by the local runner."""
        return self._spec

    def prepare(self, context: RunContext) -> StageResult:
        """Record preparation for the test stage."""
        self.events.append(f"prepare:{self.spec.name}")
        return StageResult(message=f"Prepared {self.spec.name}.")

    def run(self, context: RunContext) -> StageResult:
        """Create a deterministic output used by output validation."""
        self.events.append(f"run:{self.spec.name}")
        output = context.workspace / f"{self.spec.name}.done"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(self.spec.name, encoding="utf-8")
        return StageResult(message=f"Ran {self.spec.name}.", artifacts=(output,))

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Require the deterministic output created by `run`."""
        report = ValidationReport(subject=self.spec.name)
        output = context.workspace / f"{self.spec.name}.done"
        if not output.is_file():
            report.add("test.output", f"Output missing: {output}")
        return report


def test_workflow_spec_orders_dependencies_deterministically() -> None:
    """A specification must order each dependency before its consumer."""
    spec = WorkflowSpec.from_stages(
        "bmatrix",
        [
            StageSpec("nicas", "bmatrix.nicas", needs=("hdiag",)),
            StageSpec("nmc_pairs", "bmatrix.nmc_pairs"),
            StageSpec("hdiag", "bmatrix.hdiag", needs=("bflow",)),
            StageSpec("bflow", "bmatrix.bflow", needs=("nmc_pairs",)),
        ],
    )

    assert spec.topological_order() == ("nmc_pairs", "bflow", "hdiag", "nicas")


def test_workflow_spec_rejects_cycles() -> None:
    """A dependency cycle must fail before any runner is created."""
    with pytest.raises(WorkflowSpecificationError, match="dependency cycle"):
        WorkflowSpec.from_stages(
            "invalid",
            [
                StageSpec("first", "first", needs=("second",)),
                StageSpec("second", "second", needs=("first",)),
            ],
        )


def test_local_runner_is_restart_safe(tmp_path: Path) -> None:
    """A successful stage is reused only when its output still validates."""
    events: list[str] = []
    spec = WorkflowSpec.from_stages(
        "test",
        [
            StageSpec("first", "test.first"),
            StageSpec("second", "test.second", needs=("first",)),
        ],
    )
    runner = LocalWorkflowRunner(
        spec,
        {
            "first": RecordingStage(spec.stage("first"), events),
            "second": RecordingStage(spec.stage("second"), events),
        },
    )
    context = RunContext("test", "case", tmp_path, config={})

    first_run = runner.run(context)
    second_run = runner.run(context)

    assert [item.message for item in first_run] == ["Ran first.", "Ran second."]
    assert second_run == ()
    assert events == ["prepare:first", "run:first", "prepare:second", "run:second"]

    state = RunState.load(context.state_path, workflow="test", case="case")
    assert state.stage("first").status is StageStatus.SUCCEEDED
    assert state.stage("second").status is StageStatus.SUCCEEDED


def test_netcdf_policy_detects_consumer_incompatibility(tmp_path: Path) -> None:
    """A consumer can reject NetCDF-4 before a parallel scientific job starts."""
    path = tmp_path / "background.nc"
    path.write_bytes(b"\x89HDF\r\n\x1a\n" + b"fixture")

    assert detect_netcdf_format(path) is NetcdfFormat.NETCDF4
    report = NetcdfPolicy("mpas-smio", (NetcdfFormat.CDF5,)).validate(path)

    assert not report.is_valid
    assert report.issues[0].code == "netcdf.format"
