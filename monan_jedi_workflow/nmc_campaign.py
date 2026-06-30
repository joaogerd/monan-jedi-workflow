"""Plan and validate MPAS NMC forecast campaigns for the B-matrix workflow.

The module deliberately separates the producer and consumer repositories:
``monan-jedi-workflow`` owns data acquisition, WPS, MPAS initialization and
forecast products; ``mpas-bmatrix-global`` consumes the resulting tab-separated
BFLOW manifest. No BUMP/SABER calibration command is executed here.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .cycle_context import CycleContext, parse_cycle_time
from .input_sources import InputSource, resolve_input_source
from .provenance import file_record, stable_digest, write_json_atomic
from .stage_config import cycle_render_context, load_stage_config, render_text, resolve_path
from .workflow_plan import WorkflowConfigurationError, load_workflow_config

_MINIMUM_NMC_PAIRS = 4
_WPS_POLICIES = {"auto", "always", "never"}


class NMCCampaignError(WorkflowConfigurationError):
    """The NMC campaign declaration is incomplete or its products are invalid."""


@dataclass(frozen=True)
class ForecastProduct:
    """Expected MPAS products for one initialization time and lead."""

    init_time: str
    lead_hours: int
    valid_time: str
    restart: Path
    bflow: Path


@dataclass(frozen=True)
class NMCPair:
    """One old f048/new f024 pair valid at the same time."""

    valid_time: str
    f048: ForecastProduct
    f024: ForecastProduct


@dataclass(frozen=True)
class NMCInitialization:
    """One analysis/initial-condition time required by a campaign."""

    init_time: str
    source: InputSource
    use_wps: bool


@dataclass(frozen=True)
class NMCCampaign:
    """Fully resolved, immutable plan for a multi-pair NMC campaign."""

    config_dir: Path
    mesh: str | None
    source_name: str
    use_wps: bool
    minimum_pairs: int
    start_valid_time: str
    end_valid_time: str
    valid_interval_hours: int
    f024_hours: int
    f048_hours: int
    output_dir: Path
    pairs: tuple[NMCPair, ...]
    initializations: tuple[NMCInitialization, ...]
    fingerprint: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NMCCampaignError(f"{label} must be a mapping.")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise NMCCampaignError(f"{label} must be a non-empty string.")
    return value


def _positive_int(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise NMCCampaignError(f"{label} must be a positive integer.") from error
    if parsed < 1:
        raise NMCCampaignError(f"{label} must be a positive integer.")
    return parsed


def _cycle(value: Any, label: str) -> CycleContext:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise NMCCampaignError(f"{label} must include a UTC offset or trailing Z.")
        return CycleContext(value.astimezone(timezone.utc))
    try:
        return parse_cycle_time(_string(value, label))
    except ValueError as error:
        raise NMCCampaignError(f"{label} must be a timezone-aware ISO-8601 timestamp.") from error


def _iter_cycles(start: CycleContext, end: CycleContext, interval_hours: int) -> Iterable[CycleContext]:
    if end.value < start.value:
        raise NMCCampaignError("workflow.bmatrix.campaign.end_valid_time precedes start_valid_time.")
    current = start.value
    while current <= end.value:
        yield CycleContext(current)
        current += timedelta(hours=interval_hours)


def _wps_enabled(policy: str, source: InputSource) -> bool:
    if policy == "always":
        return True
    if policy == "never":
        return False
    return source.requires_wps


def _product_path(
    config_dir: Path,
    init: CycleContext,
    lead_hours: int,
    template: str,
    label: str,
) -> Path:
    """Resolve a lead-specific product path from the existing ``mpas.yaml`` contract."""
    config = load_stage_config(config_dir, "mpas.yaml", "mpas")
    context = cycle_render_context(init, lead_hours=lead_hours)
    run_dir_value = config.get("run_dir")
    if not isinstance(run_dir_value, str) or not run_dir_value:
        raise NMCCampaignError("mpas.run_dir must be a non-empty string.")
    run_dir = resolve_path(run_dir_value, config_dir=config_dir, context=context, label="mpas.run_dir")
    context = {**context, "run_dir": str(run_dir)}
    rendered = render_text(template, context, label=label)
    path = Path(rendered)
    return path if path.is_absolute() else run_dir / path


def _campaign_spec(config_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    workflow = load_workflow_config(config_dir)
    bmatrix = _mapping(workflow.get("bmatrix"), "workflow.bmatrix")
    campaign = _mapping(bmatrix.get("campaign"), "workflow.bmatrix.campaign")
    return workflow, bmatrix, campaign


def build_nmc_campaign(config_dir: Path) -> NMCCampaign:
    """Resolve the complete f048/f024 geometry declared in ``workflow.yaml``.

    A campaign has at least four valid times. It includes every required
    initialization time, each f024/f048 product path and the selected source for
    data retrieval/WPS. The function does not create directories, download data
    or submit jobs.
    """
    config_dir = config_dir.resolve()
    workflow, _bmatrix, spec = _campaign_spec(config_dir)
    source_name = _string(workflow.get("input_source"), "workflow.input_source")
    mesh = workflow.get("mesh")
    if mesh is not None:
        mesh = _string(mesh, "workflow.mesh")
    policy = _string(workflow.get("use_wps", "auto"), "workflow.use_wps").lower()
    if policy not in _WPS_POLICIES:
        raise NMCCampaignError(f"workflow.use_wps must be one of {sorted(_WPS_POLICIES)}.")

    start = _cycle(spec.get("start_valid_time"), "workflow.bmatrix.campaign.start_valid_time")
    end = _cycle(spec.get("end_valid_time"), "workflow.bmatrix.campaign.end_valid_time")
    interval = _positive_int(spec.get("valid_interval_hours", 24), "workflow.bmatrix.campaign.valid_interval_hours")
    minimum_pairs = _positive_int(spec.get("minimum_pairs", _MINIMUM_NMC_PAIRS), "workflow.bmatrix.campaign.minimum_pairs")
    if minimum_pairs < _MINIMUM_NMC_PAIRS:
        raise NMCCampaignError(
            f"workflow.bmatrix.campaign.minimum_pairs must be at least {_MINIMUM_NMC_PAIRS} for B-matrix calibration."
        )

    forecasts = _mapping(spec.get("forecasts", {}), "workflow.bmatrix.campaign.forecasts")
    f024_hours = _positive_int(forecasts.get("f024_hours", 24), "workflow.bmatrix.campaign.forecasts.f024_hours")
    f048_hours = _positive_int(forecasts.get("f048_hours", 48), "workflow.bmatrix.campaign.forecasts.f048_hours")
    if f048_hours <= f024_hours:
        raise NMCCampaignError("f048_hours must be greater than f024_hours.")

    products = _mapping(forecasts.get("products", {}), "workflow.bmatrix.campaign.forecasts.products")
    restart_template = _string(products.get("restart", "restart.{mpas_valid_file_time}.nc"), "workflow.bmatrix.campaign.forecasts.products.restart")
    bflow_template = _string(products.get("bflow", "mpasout.{mpas_valid_file_time}.nc"), "workflow.bmatrix.campaign.forecasts.products.bflow")
    output_dir = Path(_string(spec.get("output_dir", ".monan-jedi-workflow/nmc-campaign"), "workflow.bmatrix.campaign.output_dir"))
    if not output_dir.is_absolute():
        output_dir = config_dir / output_dir

    pairs: list[NMCPair] = []
    initialization_cycles: dict[str, CycleContext] = {}
    for valid in _iter_cycles(start, end, interval):
        old = CycleContext(valid.value - timedelta(hours=f048_hours))
        new = CycleContext(valid.value - timedelta(hours=f024_hours))
        f048 = ForecastProduct(
            init_time=old.cycle_time,
            lead_hours=f048_hours,
            valid_time=valid.cycle_time,
            restart=_product_path(config_dir, old, f048_hours, restart_template, "bmatrix f048 restart"),
            bflow=_product_path(config_dir, old, f048_hours, bflow_template, "bmatrix f048 bflow"),
        )
        f024 = ForecastProduct(
            init_time=new.cycle_time,
            lead_hours=f024_hours,
            valid_time=valid.cycle_time,
            restart=_product_path(config_dir, new, f024_hours, restart_template, "bmatrix f024 restart"),
            bflow=_product_path(config_dir, new, f024_hours, bflow_template, "bmatrix f024 bflow"),
        )
        pairs.append(NMCPair(valid.cycle_time, f048, f024))
        initialization_cycles[old.cycle_time] = old
        initialization_cycles[new.cycle_time] = new

    if len(pairs) < minimum_pairs:
        raise NMCCampaignError(
            f"Campaign declares {len(pairs)} pair(s), below required minimum {minimum_pairs}. "
            "Extend the valid-time range or reduce the interval only when scientifically justified."
        )

    initializations: list[NMCInitialization] = []
    use_wps_values: set[bool] = set()
    for init in sorted(initialization_cycles.values(), key=lambda item: item.value):
        source = resolve_input_source(config_dir, source_name, init.cycle_time)
        enabled = _wps_enabled(policy, source)
        initializations.append(NMCInitialization(init.cycle_time, source, enabled))
        use_wps_values.add(enabled)

    if len(use_wps_values) > 1:
        raise NMCCampaignError("The selected input source changes WPS applicability across campaign cycles.")
    use_wps = next(iter(use_wps_values), False)
    required = ["mpas.yaml", "mpas_init.yaml", "inputs.yaml"]
    if use_wps:
        required.append("wps.yaml")
    missing = [name for name in required if not (config_dir / name).is_file()]
    if missing:
        raise NMCCampaignError("NMC campaign requires configuration file(s): " + ", ".join(missing))

    fingerprint = stable_digest(
        {
            "workflow": workflow,
            "pairs": [asdict(pair) for pair in pairs],
            "initializations": [
                {"init_time": item.init_time, "source": item.source.name, "target": str(item.source.target), "use_wps": item.use_wps}
                for item in initializations
            ],
        }
    )
    return NMCCampaign(
        config_dir=config_dir,
        mesh=mesh,
        source_name=source_name,
        use_wps=use_wps,
        minimum_pairs=minimum_pairs,
        start_valid_time=start.cycle_time,
        end_valid_time=end.cycle_time,
        valid_interval_hours=interval,
        f024_hours=f024_hours,
        f048_hours=f048_hours,
        output_dir=output_dir,
        pairs=tuple(pairs),
        initializations=tuple(initializations),
        fingerprint=fingerprint,
    )


def campaign_plan_path(campaign: NMCCampaign) -> Path:
    start = campaign.start_valid_time.replace(":", "").replace("-", "")
    end = campaign.end_valid_time.replace(":", "").replace("-", "")
    return campaign.output_dir / f"nmc-campaign-{start}-{end}.json"


def bflow_manifest_path(campaign: NMCCampaign) -> Path:
    return campaign.output_dir / "bflow-manifest.tsv"


def write_nmc_campaign_plan(campaign: NMCCampaign, *, force: bool = False) -> Path:
    """Persist the campaign plan atomically, refusing a changed plan by default."""
    path = campaign_plan_path(campaign)
    if path.is_file() and not force:
        import json
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("fingerprint") == campaign.fingerprint:
            return path
        raise FileExistsError(f"NMC campaign changed since previous plan: {path}. Use --force to replace it.")
    payload = {
        "schema_version": 1,
        "generated_at": _timestamp(),
        "producer": "monan-jedi-workflow",
        "fingerprint": campaign.fingerprint,
        "mesh": campaign.mesh,
        "input_source": campaign.source_name,
        "use_wps": campaign.use_wps,
        "minimum_pairs": campaign.minimum_pairs,
        "start_valid_time": campaign.start_valid_time,
        "end_valid_time": campaign.end_valid_time,
        "valid_interval_hours": campaign.valid_interval_hours,
        "f024_hours": campaign.f024_hours,
        "f048_hours": campaign.f048_hours,
        "initializations": [
            {
                "init_time": item.init_time,
                "provider": item.source.provider,
                "input": str(item.source.target),
                "format": item.source.data_format,
                "use_wps": item.use_wps,
            }
            for item in campaign.initializations
        ],
        "pairs": [
            {
                "valid_time": pair.valid_time,
                "f048": {**asdict(pair.f048), "restart": str(pair.f048.restart), "bflow": str(pair.f048.bflow)},
                "f024": {**asdict(pair.f024), "restart": str(pair.f024.restart), "bflow": str(pair.f024.bflow)},
            }
            for pair in campaign.pairs
        ],
        "consumer_contract": {
            "repository": "mpas-bmatrix-global",
            "branch": "refactor/bflow-python-pipeline",
            "command": "mpasbflow all --manifest bflow-manifest.tsv",
            "manifest_columns": ["valid_time", "f048", "f024"],
        },
    }
    return write_json_atomic(path, payload)


def campaign_status(campaign: NMCCampaign, *, with_checksum: bool = False) -> dict[str, Any]:
    """Report available and missing input/forecast products without changing them."""
    inputs = []
    for item in campaign.initializations:
        entry: dict[str, Any] = {
            "init_time": item.init_time,
            "provider": item.source.provider,
            "path": str(item.source.target),
            "available": item.source.target.is_file() and item.source.target.stat().st_size > 0,
            "use_wps": item.use_wps,
        }
        if entry["available"]:
            entry["product"] = file_record(item.source.target, with_checksum=with_checksum)
        inputs.append(entry)

    pairs = []
    ready_count = 0
    for pair in campaign.pairs:
        entry: dict[str, Any] = {"valid_time": pair.valid_time}
        ready = True
        for label, product in (("f048", pair.f048), ("f024", pair.f024)):
            restart_ok = product.restart.is_file() and product.restart.stat().st_size > 0
            bflow_ok = product.bflow.is_file() and product.bflow.stat().st_size > 0
            entry[label] = {
                "init_time": product.init_time,
                "lead_hours": product.lead_hours,
                "restart": str(product.restart),
                "restart_available": restart_ok,
                "bflow": str(product.bflow),
                "bflow_available": bflow_ok,
            }
            ready = ready and restart_ok and bflow_ok
        entry["ready"] = ready
        ready_count += int(ready)
        pairs.append(entry)

    return {
        "schema_version": 1,
        "checked_at": _timestamp(),
        "fingerprint": campaign.fingerprint,
        "minimum_pairs": campaign.minimum_pairs,
        "planned_pairs": len(campaign.pairs),
        "ready_pairs": ready_count,
        "campaign_ready": ready_count >= campaign.minimum_pairs,
        "inputs": inputs,
        "pairs": pairs,
    }


def write_bflow_manifest(campaign: NMCCampaign, *, with_checksum: bool = False) -> tuple[Path, Path]:
    """Write the exact hand-off manifest accepted by ``mpasbflow --manifest``.

    Both restart and ``da_state`` products must exist for every pair. The TSV
    carries the latter because BFLOW consumes ``mpasout``, while restart files are
    retained as an independent NMC structural check.
    """
    status = campaign_status(campaign, with_checksum=with_checksum)
    if status["ready_pairs"] < campaign.minimum_pairs:
        missing = [item["valid_time"] for item in status["pairs"] if not item["ready"]]
        raise NMCCampaignError(
            f"Cannot export BFLOW manifest: only {status['ready_pairs']} of {campaign.minimum_pairs} required pair(s) are ready. "
            f"Incomplete valid times: {', '.join(missing)}"
        )
    if status["ready_pairs"] != len(campaign.pairs):
        raise NMCCampaignError("Cannot export a partial campaign; all declared pairs must be ready.")

    manifest = bflow_manifest_path(campaign)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_name(f".{manifest.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["valid_time", "f048", "f024"], delimiter="\t")
        writer.writeheader()
        for pair in campaign.pairs:
            writer.writerow({"valid_time": pair.valid_time, "f048": str(pair.f048.bflow), "f024": str(pair.f024.bflow)})
    temporary.replace(manifest)

    report = {
        **status,
        "manifest": str(manifest),
        "consumer": "mpas-bmatrix-global: mpasbflow all --manifest",
        "pairs": [
            {
                **entry,
                "f048": {**entry["f048"], "bflow_record": file_record(pair.f048.bflow, with_checksum=with_checksum)},
                "f024": {**entry["f024"], "bflow_record": file_record(pair.f024.bflow, with_checksum=with_checksum)},
            }
            for entry, pair in zip(status["pairs"], campaign.pairs)
        ],
    }
    report_path = write_json_atomic(manifest.with_suffix(".json"), report)
    return manifest, report_path
