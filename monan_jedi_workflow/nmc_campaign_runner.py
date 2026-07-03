"""Resumable execution frontiers for an NMC forecast campaign.

The runner intentionally advances one dependency layer at a time. Local input
and WPS work may complete immediately; PBS-backed init and forecast layers stop
after submission unless ``wait`` is explicitly requested. A later identical
invocation revalidates products before advancing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .init_stage import _load as _load_init_run
from .init_stage import prepare_mpas_init, submit_mpas_init, validate_mpas_init, wait_mpas_init
from .input_sources import fetch_input_source, validate_input_source
from .mpas_stage import (
    MPASValidationError,
    load_mpas_run,
    prepare_mpas,
    submit_mpas,
    validate_mpas,
    wait_mpas,
)
from .nmc_campaign import NMCCampaign, write_bflow_manifest
from .provenance import write_json_atomic
from .stage_config import load_stage_config
from .wps_stage import WPSValidationError, prepare_wps, run_wps, validate_wps


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _state_path(campaign: NMCCampaign) -> Path:
    return campaign.output_dir / "nmc-campaign-execution.json"


def _record(campaign: NMCCampaign, state: str, **details: Any) -> Path:
    return write_json_atomic(
        _state_path(campaign),
        {
            "schema_version": 1,
            "updated_at": _timestamp(),
            "fingerprint": campaign.fingerprint,
            "state": state,
            **details,
        },
    )


def _validate_forecast_layout(campaign: NMCCampaign) -> None:
    """Prevent f024/f048 from sharing a mutable MPAS working directory."""
    config = load_stage_config(campaign.config_dir, "mpas.yaml", "mpas")
    run_dir = config.get("run_dir")
    if not isinstance(run_dir, str) or "{lead_hours}" not in run_dir:
        raise ValueError(
            "NMC campaigns require mpas.run_dir to include '{lead_hours}' so f024 and f048 "
            "for the same initialization cannot overwrite each other."
        )


def _ensure_inputs_and_wps(campaign: NMCCampaign, *, fetch_inputs: bool) -> None:
    for item in campaign.initializations:
        source = item.source
        if not source.target.is_file():
            if not fetch_inputs:
                raise FileNotFoundError(
                    f"Campaign input is absent: {source.target}. Re-run with --fetch-inputs only for configured remote providers."
                )
            fetch_input_source(source)
        validate_input_source(source, required_mesh=campaign.mesh)
        if not item.use_wps:
            continue
        try:
            validate_wps(campaign.config_dir, item.init_time)
        except (FileNotFoundError, WPSValidationError):
            prepare_wps(campaign.config_dir, item.init_time)
            run_wps(campaign.config_dir, item.init_time)
            validate_wps(campaign.config_dir, item.init_time)


def _missing_initializations(campaign: NMCCampaign) -> list[str]:
    missing: list[str] = []
    for item in campaign.initializations:
        try:
            validate_mpas_init(campaign.config_dir, item.init_time)
        except (FileNotFoundError, RuntimeError):
            missing.append(item.init_time)
    return missing


def _prepare_initializations(campaign: NMCCampaign, missing: list[str]) -> list[str]:
    prepared: list[str] = []
    for init_time in missing:
        run = _load_init_run(campaign.config_dir, init_time)
        if not run.manifest_path.exists():
            prepare_mpas_init(campaign.config_dir, init_time)
            prepared.append(init_time)
    return prepared


def _submit_initializations(
    campaign: NMCCampaign,
    missing: list[str],
    *,
    wait: bool,
    resubmit: bool,
    poll_seconds: int,
) -> dict[str, str]:
    jobs: dict[str, str] = {}
    for init_time in missing:
        job_id = submit_mpas_init(
            campaign.config_dir,
            init_time,
            resubmit=resubmit,
            wait=False,
            poll_seconds=poll_seconds,
        )
        jobs[init_time] = job_id
        if wait:
            wait_mpas_init(campaign.config_dir, init_time, poll_seconds=poll_seconds)
            validate_mpas_init(campaign.config_dir, init_time)
    return jobs


def _forecast_keys(campaign: NMCCampaign) -> list[tuple[str, int]]:
    keys = {(pair.f048.init_time, pair.f048.lead_hours) for pair in campaign.pairs}
    keys.update((pair.f024.init_time, pair.f024.lead_hours) for pair in campaign.pairs)
    return sorted(keys)


def _missing_forecasts(campaign: NMCCampaign) -> list[tuple[str, int]]:
    missing: list[tuple[str, int]] = []
    for init_time, lead_hours in _forecast_keys(campaign):
        try:
            validate_mpas(campaign.config_dir, init_time, lead_hours=lead_hours)
        except (FileNotFoundError, MPASValidationError):
            missing.append((init_time, lead_hours))
    return missing


def _prepare_forecasts(campaign: NMCCampaign, missing: list[tuple[str, int]]) -> list[dict[str, object]]:
    prepared: list[dict[str, object]] = []
    for init_time, lead_hours in missing:
        run = load_mpas_run(campaign.config_dir, init_time, lead_hours=lead_hours)
        if not run.manifest_path.exists():
            prepare_mpas(campaign.config_dir, init_time, lead_hours=lead_hours)
            prepared.append({"init_time": init_time, "lead_hours": lead_hours})
    return prepared


def _submit_forecasts(
    campaign: NMCCampaign,
    missing: list[tuple[str, int]],
    *,
    wait: bool,
    resubmit: bool,
    poll_seconds: int,
    timeout_seconds: int | None,
) -> dict[str, str]:
    jobs: dict[str, str] = {}
    for init_time, lead_hours in missing:
        job_id = submit_mpas(
            campaign.config_dir,
            init_time,
            lead_hours=lead_hours,
            resubmit=resubmit,
            wait=False,
            poll_seconds=poll_seconds,
            timeout_seconds=timeout_seconds,
        )
        jobs[f"{init_time}|f{lead_hours:03d}"] = job_id
        if wait:
            wait_mpas(
                campaign.config_dir,
                init_time,
                lead_hours=lead_hours,
                poll_seconds=poll_seconds,
                timeout_seconds=timeout_seconds,
            )
            validate_mpas(campaign.config_dir, init_time, lead_hours=lead_hours)
    return jobs


def execute_nmc_campaign(
    campaign: NMCCampaign,
    *,
    submit: bool = False,
    wait: bool = False,
    resubmit: bool = False,
    fetch_inputs: bool = False,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
) -> Path:
    """Advance one safe frontier of the campaign and persist its execution state.

    With no ``submit`` flag, the function only prepares missing PBS stages. With
    ``submit`` but no ``wait``, it submits every missing independent job in the
    current layer and returns. This prevents a later layer from starting before
    validated products exist.
    """
    if wait and not submit:
        raise ValueError("--wait requires --submit.")
    _validate_forecast_layout(campaign)
    _ensure_inputs_and_wps(campaign, fetch_inputs=fetch_inputs)

    missing_init = _missing_initializations(campaign)
    if missing_init:
        prepared = _prepare_initializations(campaign, missing_init)
        if not submit:
            return _record(campaign, "prepared-init", prepared=prepared, pending=missing_init)
        jobs = _submit_initializations(
            campaign,
            missing_init,
            wait=wait,
            resubmit=resubmit,
            poll_seconds=poll_seconds,
        )
        if not wait:
            return _record(campaign, "submitted-init", jobs=jobs, pending=missing_init)
        return _record(campaign, "validated-init", jobs=jobs)

    missing_forecast = _missing_forecasts(campaign)
    if missing_forecast:
        prepared = _prepare_forecasts(campaign, missing_forecast)
        if not submit:
            return _record(campaign, "prepared-forecast", prepared=prepared, pending=missing_forecast)
        jobs = _submit_forecasts(
            campaign,
            missing_forecast,
            wait=wait,
            resubmit=resubmit,
            poll_seconds=poll_seconds,
            timeout_seconds=timeout_seconds,
        )
        if not wait:
            return _record(campaign, "submitted-forecast", jobs=jobs, pending=missing_forecast)
        return _record(campaign, "validated-forecast", jobs=jobs)

    manifest, report = write_bflow_manifest(campaign)
    return _record(campaign, "exported-bflow-manifest", manifest=str(manifest), report=str(report))
