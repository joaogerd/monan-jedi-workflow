"""Execute one scheduler-neutral stage as an orchestration task."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.stage import RunContext, Stage, StageResult
from ...core.state import RunState, StageStatus
from ...core.workflow_spec import WorkflowSpec


class StageTaskRunner:
    """Run one named stage after validating declared dependency artifacts.

    This task-level executor is used by external orchestration backends. It
    shares the `Stage` lifecycle and persisted `RunState` contract with the
    local workflow runner, while intentionally executing only one task.
    """

    def __init__(self, specification: WorkflowSpec, stages: Mapping[str, Stage]) -> None:
        self.specification = specification
        self.stages = dict(stages)

    def run(self, context: RunContext, name: str, *, force: bool = False) -> StageResult | None:
        """Execute one stage or reuse its still-valid published outputs.

        Parameters
        ----------
        context : RunContext
            Resolved workflow run context.
        name : str
            Stage identifier from the workflow specification.
        force : bool, default=False
            Re-run a previously successful stage.

        Returns
        -------
        StageResult | None
            Stage result, or ``None`` when prior outputs remain valid.
        """
        stage_spec = self.specification.stage(name)
        stage = self.stages[name]
        if context.dry_run:
            return stage.plan(context)

        # Scheduler dependencies establish ordering; artifact validation makes
        # that ordering scientifically meaningful before input consumption.
        for dependency in stage_spec.needs:
            self.stages[dependency].validate_outputs(context).require_valid()

        state = RunState.load(context.state_path, workflow=context.workflow, case=context.case)
        stage_state = state.stage(name)
        if stage_state.status is StageStatus.SUCCEEDED and not force:
            if stage.validate_outputs(context).is_valid:
                return None
            stage_state.transition(StageStatus.PLANNED, message="Output validation requires rerun.")
        elif stage_state.status is StageStatus.SUCCEEDED and force:
            stage_state.transition(StageStatus.PLANNED, message="Forced rerun requested.")
        elif stage_state.status is StageStatus.RUNNING:
            stage_state.transition(StageStatus.FAILED, message="Previous execution ended with unknown state.")
            stage_state.transition(StageStatus.PLANNED, message="Retrying after unknown running state.")
        elif stage_state.status in {StageStatus.FAILED, StageStatus.SKIPPED}:
            stage_state.transition(StageStatus.PLANNED, message="Retry requested by task runner.")
        state.save(context.state_path)

        try:
            inputs = stage.validate_inputs(context)
            inputs.require_valid()
            prepared = stage.prepare(context)
            stage_state.transition(StageStatus.PREPARED, message=prepared.message)
            state.save(context.state_path)
            stage_state.transition(StageStatus.RUNNING, message=f"Running {name}.")
            state.save(context.state_path)
            result = stage.submit(context)
            stage.wait(context)
            outputs = stage.validate_outputs(context)
            outputs.require_valid()
            final = stage.finalize(context)
            stage_state.transition(StageStatus.SUCCEEDED, message=final.message or result.message)
            state.save(context.state_path)
            return result
        except Exception as exc:
            stage_state.transition(StageStatus.FAILED, message=str(exc))
            state.save(context.state_path)
            raise
