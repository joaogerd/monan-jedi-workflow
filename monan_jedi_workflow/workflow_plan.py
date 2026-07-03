"""High-level, declarative MPAS workflow planning and safe resumption."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cycle_context import CycleContext, parse_cycle_time
from .input_sources import (
    InputSource,
    InputValidationError,
    resolve_input_source,
    validate_input_source,
    write_input_report,
)
from .provenance import file_record, stable_digest, write_json_atomic
from .yaml_utils import load_yaml_file

_MODES = {"prepare", "forecast", "cycle", "bmatrix"}
_WPS_POLICIES = {"auto", "always", "never"}


class WorkflowConfigurationError(ValueError):
    """The high-level workflow YAML is incomplete or inconsistent."""


@dataclass(frozen=True)
class PlanStep:
    """One externally visible workflow action and its declared prerequisites."""

    name: str
    command: list[str]
    purpose: str
    depends_on: tuple[str, ...] = ()
    execution: str = "local"


@dataclass(frozen=True)
class WorkflowPlan:
    """Resolved workflow graph for a single cycle and operating mode."""

    cycle: CycleContext
    mode: str
    config_dir: Path
    source: InputSource
    use_wps: bool
    mesh: str | None
    steps: tuple[PlanStep, ...]
    fingerprint: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowConfigurationError(f"{label} must be a mapping.")
    return value


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise WorkflowConfigurationError(f"{label} must be true or false.")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise WorkflowConfigurationError(f"{label} must be a non-empty string.")
    return value


def load_workflow_config(config_dir: Path) -> dict[str, Any]:
    """Load the high-level workflow declaration from ``workflow.yaml``."""
    document = load_yaml_file(config_dir.resolve() / "workflow.yaml")
    return _mapping(document.get("workflow"), "workflow.yaml.workflow")


def _stage_enabled(config: dict[str, Any], name: str, default: bool) -> bool:
    stages = config.get("stages", {})
    if stages is None:
        stages = {}
    stages = _mapping(stages, "workflow.stages")
    return _bool(stages.get(name, default), f"workflow.stages.{name}")


def _requires_wps(policy: str, source: InputSource) -> bool:
    if policy == "always":
        return True
    if policy == "never":
        return False
    return source.requires_wps


def _required_file(config_dir: Path, filename: str, label: str) -> None:
    if not (config_dir / filename).is_file():
        raise WorkflowConfigurationError(
            f"{label} requires {filename} in the experiment configuration directory: {config_dir}"
        )


def _base_steps(source: InputSource) -> list[PlanStep]:
    steps = [
        PlanStep(
            name="inputs-validate",
            command=["input-validate", "--source", source.name],
            purpose="validate availability, coverage, format declaration and integrity of the selected input",
        )
    ]
    if source.provider not in {"local", "infrastructure"}:
        steps.append(
            PlanStep(
                name="inputs-fetch",
                command=["input-fetch", "--source", source.name],
                purpose="explicitly fetch the remote source when it is not present locally",
                depends_on=("inputs-validate",),
                execution="explicit",
            )
        )
    return steps


def build_workflow_plan(config_dir: Path, cycle_time: str) -> WorkflowPlan:
    """Build and validate a deterministic stage graph without executing it."""
    config_dir = config_dir.resolve()
    config = load_workflow_config(config_dir)
    mode = _string(config.get("mode"), "workflow.mode").lower()
    if mode not in _MODES:
        raise WorkflowConfigurationError(f"workflow.mode must be one of {sorted(_MODES)}.")
    source_name = _string(config.get("input_source"), "workflow.input_source")
    policy = _string(config.get("use_wps", "auto"), "workflow.use_wps").lower()
    if policy not in _WPS_POLICIES:
        raise WorkflowConfigurationError(f"workflow.use_wps must be one of {sorted(_WPS_POLICIES)}.")
    cycle = parse_cycle_time(cycle_time)
    source = resolve_input_source(config_dir, source_name, cycle_time)
    mesh = config.get("mesh")
    if mesh is not None:
        mesh = _string(mesh, "workflow.mesh")

    use_wps = _requires_wps(policy, source)
    enable_init = _stage_enabled(config, "mpas_init", mode in {"prepare", "forecast", "cycle", "bmatrix"})
    enable_forecast = _stage_enabled(config, "forecast", mode in {"forecast", "cycle", "bmatrix"})
    enable_assimilation = _stage_enabled(config, "assimilation", mode == "cycle")
    enable_bmatrix = _stage_enabled(config, "bmatrix", mode == "bmatrix")

    if use_wps:
        _required_file(config_dir, "wps.yaml", "WPS stage")
    if enable_init:
        _required_file(config_dir, "mpas_init.yaml", "MPAS initial-condition stage")
    if enable_forecast:
        _required_file(config_dir, "mpas.yaml", "MPAS forecast stage")
    if enable_assimilation:
        for filename in ("experiment.yaml", "variables.yaml", "observations.yaml", "runtime.yaml", "pbs.yaml"):
            _required_file(config_dir, filename, "MPAS-JEDI assimilation stage")

    steps = _base_steps(source)
    last = steps[-1].name
    if use_wps:
        steps.extend(
            [
                PlanStep("wps-prepare", ["wps-prepare"], "stage WPS tools, GRIB and rendered namelist", (last,)),
                PlanStep("wps-run", ["wps-run"], "run link_grib and ungrib without shell evaluation", ("wps-prepare",)),
                PlanStep("wps-validate", ["wps-validate"], "validate WPS intermediate product", ("wps-run",)),
            ]
        )
        last = "wps-validate"
    if enable_init:
        steps.extend(
            [
                PlanStep("mpas-init-prepare", ["mpas-init-prepare"], "render and stage MPAS initialization inputs", (last,)),
                PlanStep("mpas-init-submit", ["mpas-init-submit"], "submit MPAS initial-condition generation", ("mpas-init-prepare",), "scheduler"),
                PlanStep("mpas-init-validate", ["mpas-init-validate"], "validate MPAS initialization product", ("mpas-init-submit",)),
            ]
        )
        last = "mpas-init-validate"
    if enable_forecast:
        steps.extend(
            [
                PlanStep("mpas-prepare", ["mpas-prepare"], "render and stage MPAS forecast run", (last,)),
                PlanStep("mpas-submit", ["mpas-submit"], "submit MPAS forecast", ("mpas-prepare",), "scheduler"),
                PlanStep("mpas-validate", ["mpas-validate"], "validate MPAS forecast products", ("mpas-submit",)),
            ]
        )
        last = "mpas-validate"
    if enable_assimilation:
        steps.extend(
            [
                PlanStep("jedi-prepare-runtime", ["prepare-runtime"], "prepare isolated MPAS-JEDI runtime", (last,)),
                PlanStep("jedi-render-yaml", ["render-yaml"], "compose MPAS-JEDI YAML from fragments", ("jedi-prepare-runtime",)),
                PlanStep("jedi-render-pbs", ["render-pbs"], "render scheduler adapter", ("jedi-render-yaml",)),
                PlanStep("jedi-submit", ["submit"], "submit MPAS-JEDI assimilation", ("jedi-render-pbs",), "scheduler"),
                PlanStep("jedi-validate", ["validate-run"], "validate declared assimilation products", ("jedi-submit",)),
            ]
        )
        last = "jedi-validate"
    if enable_bmatrix:
        steps.append(
            PlanStep(
                "bmatrix-export-contract",
                ["prepare-bmatrix"],
                "export validated MPAS sample provenance for mpas-bmatrix-global",
                (last,),
            )
        )

    fingerprint = stable_digest(
        {
            "workflow": config,
            "cycle_time": cycle.cycle_time,
            "source": {"name": source.name, "provider": source.provider, "target": str(source.target)},
            "use_wps": use_wps,
            "steps": [asdict(step) for step in steps],
        }
    )
    return WorkflowPlan(cycle, mode, config_dir, source, use_wps, mesh, tuple(steps), fingerprint)


def workflow_state_path(plan: WorkflowPlan) -> Path:
    return plan.config_dir / ".monan-jedi-workflow" / plan.cycle.cycle_id / "workflow-plan.json"


def write_workflow_plan(plan: WorkflowPlan, *, force: bool = False) -> Path:
    """Persist a plan atomically and reuse an equivalent plan by default."""
    path = workflow_state_path(plan)
    if path.is_file() and not force:
        import json
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise WorkflowConfigurationError(f"Invalid existing workflow state: {path}") from error
        if existing.get("fingerprint") == plan.fingerprint:
            return path
        raise FileExistsError(
            f"Workflow plan changed since the previous run: {path}. Use --force to record a new plan."
        )
    payload = {
        "schema_version": 1,
        "generated_at": _timestamp(),
        "fingerprint": plan.fingerprint,
        "cycle_time": plan.cycle.cycle_time,
        "mode": plan.mode,
        "mesh": plan.mesh,
        "input_source": {
            "name": plan.source.name,
            "provider": plan.source.provider,
            "target": str(plan.source.target),
            "format": plan.source.data_format,
            "requires_wps": plan.source.requires_wps,
        },
        "use_wps": plan.use_wps,
        "steps": [asdict(step) for step in plan.steps],
    }
    return write_json_atomic(path, payload)


def validate_workflow_plan(plan: WorkflowPlan, *, with_checksum: bool = False) -> dict[str, Any]:
    """Validate source-level prerequisites and return a report usable by a CLI."""
    report = validate_input_source(plan.source, required_mesh=plan.mesh, with_checksum=with_checksum)
    report["workflow"] = {
        "mode": plan.mode,
        "cycle_time": plan.cycle.cycle_time,
        "requires_wps": plan.use_wps,
        "fingerprint": plan.fingerprint,
        "steps": [step.name for step in plan.steps],
    }
    return report


def validate_and_record_inputs(plan: WorkflowPlan, *, with_checksum: bool = False) -> Path:
    """Validate selected input and persist its provenance for a later restart."""
    return write_input_report(plan.config_dir, plan.source, validate_workflow_plan(plan, with_checksum=with_checksum))


def export_bmatrix_contract(plan: WorkflowPlan, *, with_checksum: bool = False) -> Path:
    """Export a generic, validated hand-off manifest for ``mpas-bmatrix-global``.

    The document contains MPAS sample files and provenance only. It does not run
    VBAL, HDIAG, NICAS, SO or any command from the B-matrix repository.
    """
    if plan.mode != "bmatrix":
        raise WorkflowConfigurationError("prepare-bmatrix is only valid when workflow.mode is 'bmatrix'.")
    config = load_workflow_config(plan.config_dir)
    spec = _mapping(config.get("bmatrix"), "workflow.bmatrix")
    sample_glob = _string(spec.get("sample_glob"), "workflow.bmatrix.sample_glob")
    output_dir_value = _string(spec.get("output_dir", ".monan-jedi-workflow/bmatrix"), "workflow.bmatrix.output_dir")
    output_dir = Path(output_dir_value)
    if not output_dir.is_absolute():
        output_dir = plan.config_dir / output_dir
    samples = sorted(path for path in plan.config_dir.glob(sample_glob) if path.is_file())
    min_samples = int(spec.get("minimum_samples", 1))
    if min_samples < 1:
        raise WorkflowConfigurationError("workflow.bmatrix.minimum_samples must be at least 1.")
    if len(samples) < min_samples:
        raise InputValidationError(
            f"B-matrix hand-off requires at least {min_samples} sample(s); found {len(samples)} using {sample_glob!r}."
        )
    payload = {
        "schema_version": 1,
        "created_at": _timestamp(),
        "producer": "monan-jedi-workflow",
        "cycle_time": plan.cycle.cycle_time,
        "mesh": plan.mesh,
        "input_source": plan.source.name,
        "workflow_fingerprint": plan.fingerprint,
        "samples": [file_record(path, with_checksum=with_checksum) for path in samples],
        "consumer_contract": {
            "repository": "mpas-bmatrix-global",
            "pipeline": "refactor/bflow-python-pipeline",
            "expected_next_steps": ["VBAL", "HDIAG", "NICAS", "DIRAC", "SO"],
            "note": "The producer does not execute the B-matrix calibration pipeline.",
        },
    }
    return write_json_atomic(output_dir / f"bmatrix-inputs-{plan.cycle.cycle_id}.json", payload)


def _execution_state_path(plan: WorkflowPlan) -> Path:
    return workflow_state_path(plan).with_name("workflow-execution.json")


def _record_execution(plan: WorkflowPlan, state: str, **details: Any) -> Path:
    return write_json_atomic(
        _execution_state_path(plan),
        {
            "schema_version": 1,
            "updated_at": _timestamp(),
            "cycle_time": plan.cycle.cycle_time,
            "mode": plan.mode,
            "fingerprint": plan.fingerprint,
            "state": state,
            **details,
        },
    )


def execute_workflow(
    plan: WorkflowPlan,
    *,
    submit: bool = False,
    resubmit: bool = False,
    fetch_inputs: bool = False,
) -> Path:
    """Execute only the next safe frontier of a planned workflow.

    PBS submission is permitted only when ``submit`` is explicitly true. After a
    submission this function records the job frontier and returns; a later call
    validates products before it advances to the next stage.
    """
    from . import cli as jedi_cli
    from .init_stage import prepare_mpas_init, submit_mpas_init, validate_mpas_init
    from .input_sources import fetch_input_source
    from .mpas_stage import MPASValidationError, prepare_mpas, submit_mpas, validate_mpas
    from .wps_stage import WPSValidationError, prepare_wps, run_wps, validate_wps

    if not plan.source.target.is_file():
        if not fetch_inputs:
            raise InputValidationError(
                f"Input is missing: {plan.source.target}. Re-run with --fetch-inputs only for a configured remote source."
            )
        fetch_input_source(plan.source)
    input_report = validate_and_record_inputs(plan, with_checksum=False)
    names = {step.name for step in plan.steps}

    if "wps-prepare" in names:
        try:
            validate_wps(plan.config_dir, plan.cycle.cycle_time)
        except (FileNotFoundError, WPSValidationError):
            prepare_wps(plan.config_dir, plan.cycle.cycle_time)
            run_wps(plan.config_dir, plan.cycle.cycle_time)
            validate_wps(plan.config_dir, plan.cycle.cycle_time)

    if "mpas-init-prepare" in names:
        try:
            validate_mpas_init(plan.config_dir, plan.cycle.cycle_time)
        except (FileNotFoundError, RuntimeError):
            prepare_mpas_init(plan.config_dir, plan.cycle.cycle_time)
            if not submit:
                return _record_execution(plan, "prepared-mpas-init", input_report=str(input_report))
            job_id = submit_mpas_init(plan.config_dir, plan.cycle.cycle_time, resubmit=resubmit)
            return _record_execution(plan, "submitted-mpas-init", input_report=str(input_report), job_id=job_id)

    if "mpas-prepare" in names:
        try:
            validate_mpas(plan.config_dir, plan.cycle.cycle_time)
        except (FileNotFoundError, MPASValidationError):
            prepare_mpas(plan.config_dir, plan.cycle.cycle_time)
            if not submit:
                return _record_execution(plan, "prepared-mpas", input_report=str(input_report))
            job_id = submit_mpas(plan.config_dir, plan.cycle.cycle_time, resubmit=resubmit)
            return _record_execution(plan, "submitted-mpas", input_report=str(input_report), job_id=job_id)

    if "jedi-prepare-runtime" in names:
        jedi_cli.run_prepare(plan.config_dir)
        jedi_cli.run_render_yaml(plan.config_dir)
        jedi_cli.run_render_pbs(plan.config_dir)
        if not submit:
            return _record_execution(plan, "prepared-jedi", input_report=str(input_report))
        jedi_cli.run_submit(plan.config_dir, resubmit=resubmit)
        return _record_execution(plan, "submitted-jedi", input_report=str(input_report))

    if "bmatrix-export-contract" in names:
        handoff = export_bmatrix_contract(plan)
        return _record_execution(plan, "exported-bmatrix-contract", input_report=str(input_report), handoff=str(handoff))

    return _record_execution(plan, "completed", input_report=str(input_report))
