"""Restart-safe local executor for scheduler-neutral workflow specifications."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.stage import RunContext, Stage, StageResult
from ...core.state import RunState, StageStatus
from ...core.workflow_spec import WorkflowSpec, WorkflowSpecificationError


class LocalWorkflowRunner:
    """Execute a workflow specification synchronously in dependency order.

    Parameters
    ----------
    specification : WorkflowSpec
        Scheduler-neutral workflow graph to execute.
    stages : Mapping[str, Stage]
        Implementations keyed by the stage names declared in the specification.

    Raises
    ------
    WorkflowSpecificationError
        Raised when stage implementations do not exactly match the workflow
        specification.
    """

    def __init__(self, specification: WorkflowSpec, stages: Mapping[str, Stage]) -> None:
        self.specification = specification
        self.stages = dict(stages)
        self._validate_implementations()

    def _validate_implementations(self) -> None:
        expected = {item.name for item in self.specification.stages}
        received = set(self.stages)
        missing = expected.difference(received)
        extra = received.difference(expected)
        if missing or extra:
            details: list[str] = []
            if missing:
                details.append("missing=" + ",".join(sorted(missing)))
            if extra:
                details.append("extra=" + ",".join(sorted(extra)))
            raise WorkflowSpecificationError("Stage implementation mismatch: " + "; ".join(details))
        for name, stage in self.stages.items():
            if stage.spec.name != name:
                raise WorkflowSpecificationError(
                    f"Stage mapping key '{name}' does not match implementation '{stage.spec.name}'."
                )

    def plan(self, context: RunContext) -> tuple[StageResult, ...]:
        """Plan every stage without modifying stage state.

        Parameters
        ----------
        context : RunContext
            Resolved workflow run context.

        Returns
        -------
        tuple[StageResult, ...]
            Plan results in dependency order.
        """
        return tuple(self.stages[name].plan(context) for name in self.specification.topological_order())

    def _validate_dependencies(self, context: RunContext, name: str) -> None:
        """Require valid artifacts from every declared upstream stage.

        Topological order establishes local execution order. Re-validating
        dependency artifacts prevents a downstream stage from trusting a stale
        success record after an upstream product is removed or corrupted.
        """
        for dependency in self.specification.stage(name).needs:
            self.stages[dependency].validate_outputs(context).require_valid()

    def _normalize_state(
        self,
        state: RunState,
        name: str,
        stage: Stage,
        context: RunContext,
        *,
        force: bool,
    ) -> bool:
        """Normalize persisted state and return whether valid output is reusable."""
        stage_state = state.stage(name)
        if stage_state.status is StageStatus.RUNNING:
            # A fresh local process cannot prove an inherited run is still
            # active. Platform-specific job inspection belongs to the backend;
            # local execution records a retryable failure instead of guessing.
            stage_state.transition(StageStatus.FAILED, message="Previous execution ended with unknown state.")
            stage_state.transition(StageStatus.PLANNED, message="Retrying after unknown running state.")
            state.save(context.state_path)
        elif stage_state.status is StageStatus.SUCCEEDED:
            if not force and stage.validate_outputs(context).is_valid:
                return True
            message = "Forced rerun requested." if force else "Output validation requires rerun."
            stage_state.transition(StageStatus.PLANNED, message=message)
            state.save(context.state_path)
        elif stage_state.status in {StageStatus.FAILED, StageStatus.SKIPPED}:
            stage_state.transition(StageStatus.PLANNED, message="Retry requested by workflow runner.")
            state.save(context.state_path)
        return False

    def run(self, context: RunContext, *, force: bool = False) -> tuple[StageResult, ...]:
        """Run all eligible stages in deterministic dependency order.

        Successful stages are reused only when their outputs still validate and
        `force` is false. Interrupted `running` state is retried safely rather
        than attempting an invalid lifecycle transition.
        """
        if context.dry_run:
            return self.plan(context)

        state = RunState.load(context.state_path, workflow=context.workflow, case=context.case)
        results: list[StageResult] = []
        for name in self.specification.topological_order():
            stage = self.stages[name]
            self._validate_dependencies(context, name)
            if self._normalize_state(state, name, stage, context, force=force):
                continue

            stage_state = state.stage(name)
            try:
                input_report = stage.validate_inputs(context)
                input_report.require_valid()

                prepared = stage.prepare(context)
                stage_state.transition(StageStatus.PREPARED, message=prepared.message)
                state.save(context.state_path)

                stage_state.transition(StageStatus.RUNNING, message=f"Running {name}.")
                state.save(context.state_path)
                result = stage.submit(context)
                stage.wait(context)

                output_report = stage.validate_outputs(context)
                output_report.require_valid()
                final = stage.finalize(context)

                stage_state.transition(
                    StageStatus.SUCCEEDED,
                    message=final.message or result.message,
                )
                state.save(context.state_path)
                results.append(result)
            except Exception as exc:
                if stage_state.status is not StageStatus.FAILED:
                    stage_state.transition(StageStatus.FAILED, message=str(exc))
                else:
                    stage_state.transition(StageStatus.FAILED, message=str(exc))
                state.save(context.state_path)
                raise
        return tuple(results)
