"""Restart-safe local executor for scheduler-neutral workflow specifications."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.stage import RunContext, Stage, StageResult
from ...core.state import RunState, StageStatus
from ...core.workflow_spec import WorkflowSpec, WorkflowSpecificationError


class LocalWorkflowRunner:
    """Execute workflow stages in dependency order with restart-safe reuse."""

    def __init__(self, specification: WorkflowSpec, stages: Mapping[str, Stage]) -> None:
        self.specification = specification
        self.stages = dict(stages)
        expected, received = {item.name for item in specification.stages}, set(stages)
        if expected != received:
            raise WorkflowSpecificationError(
                f"Stage implementation mismatch: missing={sorted(expected - received)}, extra={sorted(received - expected)}."
            )
        for name, stage in self.stages.items():
            if stage.spec.name != name:
                raise WorkflowSpecificationError(f"Stage mapping key '{name}' does not match implementation '{stage.spec.name}'.")

    def plan(self, context: RunContext) -> tuple[StageResult, ...]:
        """Plan all stages without modifying persistent state."""
        return tuple(self.stages[name].plan(context) for name in self.specification.topological_order())

    def _dependencies_valid(self, context: RunContext, name: str) -> None:
        """Validate every declared upstream artifact contract."""
        for dependency in self.specification.stage(name).needs:
            self.stages[dependency].validate_outputs(context).require_valid()

    def _reusable(self, state: RunState, context: RunContext, name: str, stage: Stage, force: bool) -> bool:
        """Normalize persisted state and decide whether output can be reused."""
        item = state.stage(name)
        if item.status is StageStatus.RUNNING:
            item.transition(StageStatus.FAILED, message="Previous execution ended with unknown state.")
            item.transition(StageStatus.PLANNED, message="Retrying after unknown running state.")
        elif item.status is StageStatus.SUCCEEDED:
            if not force and stage.validate_outputs(context).is_valid:
                return True
            item.transition(StageStatus.PLANNED, message="Forced rerun requested." if force else "Output validation requires rerun.")
        elif item.status in {StageStatus.FAILED, StageStatus.SKIPPED}:
            item.transition(StageStatus.PLANNED, message="Retry requested by workflow runner.")
        state.save(context.state_path)
        return False

    def run(self, context: RunContext, *, force: bool = False) -> tuple[StageResult, ...]:
        """Run stages and invalidate downstream reuse after upstream regeneration."""
        if context.dry_run:
            return self.plan(context)
        state = RunState.load(context.state_path, workflow=context.workflow, case=context.case)
        results: list[StageResult] = []
        regenerated: set[str] = set()
        for name in self.specification.topological_order():
            stage = self.stages[name]
            spec = self.specification.stage(name)
            self._dependencies_valid(context, name)
            rerun = force or any(dependency in regenerated for dependency in spec.needs)
            if self._reusable(state, context, name, stage, rerun):
                continue
            item = state.stage(name)
            try:
                stage.validate_inputs(context).require_valid()
                prepared = stage.prepare(context)
                item.transition(StageStatus.PREPARED, message=prepared.message)
                state.save(context.state_path)
                item.transition(StageStatus.RUNNING, message=f"Running {name}.")
                state.save(context.state_path)
                result = stage.submit(context)
                stage.wait(context)
                stage.validate_outputs(context).require_valid()
                final = stage.finalize(context)
                item.transition(StageStatus.SUCCEEDED, message=final.message or result.message)
                state.save(context.state_path)
                results.append(result)
                regenerated.add(name)
            except Exception as exc:
                item.transition(StageStatus.FAILED, message=str(exc))
                state.save(context.state_path)
                raise
        return tuple(results)
