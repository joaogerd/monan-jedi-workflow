"""High-level campaign interface for reproducible MONAN-JEDI experiments.

The user-facing contract is intentionally small: one campaign YAML describes
what period to run and which validated profile to use.  This module owns the
preflight, clean materialization and simpleWorkflow invocation so operators do
not need to remember the lower-level JEDI/MPAS/Obs2IODA command sequence.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .corrected_campaign import (
    _cycles,
    _iso,
    _parse_cycle,
    materialize_corrected_campaign,
)
from .corrected_replay import _initial_inputs
from .obs2ioda_stage import _build_plan, load_obs2ioda_run
from .stage_config import StageConfigurationError

_DURATION = re.compile(r"^PT(?P<hours>[1-9][0-9]*)H$")
_UNRESOLVED_ENV = re.compile(r"\$\{[^}]+\}")


@dataclass(frozen=True)
class CampaignSpec:
    """Resolved user campaign request."""

    config_path: Path
    name: str
    start_cycle: str
    end_cycle: str
    duration_hours: int
    destination: Path
    initial_jedi_case: Path
    cycling_jedi_case: Path
    mpas_case: Path
    obs2ioda_config: Path
    swf_command: tuple[str, ...]

    @property
    def workdir(self) -> Path:
        return self.destination / ".simpleworkflow"

    @property
    def workflow_path(self) -> Path:
        return self.destination / "workflow.yaml"


@dataclass(frozen=True)
class PreflightItem:
    label: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    spec: CampaignSpec
    items: tuple[PreflightItem, ...]

    @property
    def valid(self) -> bool:
        return all(item.ok for item in self.items)


def _load_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise FileNotFoundError(f"{label} file does not exist: {path}") from None
    if not isinstance(value, dict):
        raise StageConfigurationError(f"{label} root must be a mapping: {path}")
    return value


def _expand_env(value: Any, *, label: str) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item, label=f"{label}.{key}") for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item, label=label) for item in value]
    if not isinstance(value, str):
        return value
    expanded = os.path.expandvars(value)
    if _UNRESOLVED_ENV.search(expanded):
        raise StageConfigurationError(
            f"{label} contains an environment variable that is not defined: {value}"
        )
    return expanded


def _required_string(mapping: dict[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StageConfigurationError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve(strict=False)


def _profile(config: dict[str, Any], config_dir: Path) -> tuple[dict[str, Any], Path]:
    raw = config.get("profile")
    if isinstance(raw, dict):
        return _expand_env(raw, label="profile"), config_dir
    if not isinstance(raw, str) or not raw:
        raise StageConfigurationError(
            "campaign profile must be a mapping or a path to a profile YAML file"
        )
    profile_path = _resolve_path(_expand_env(raw, label="profile"), config_dir)
    document = _expand_env(_load_mapping(profile_path, "profile"), label="profile")
    profile = document.get("profile", document)
    if not isinstance(profile, dict):
        raise StageConfigurationError(f"profile must be a mapping: {profile_path}")
    return profile, profile_path.parent


def _parse_duration(value: str) -> int:
    match = _DURATION.fullmatch(value)
    if match is None:
        raise StageConfigurationError(
            "campaign.duration must use an hourly ISO-8601 form such as PT72H"
        )
    hours = int(match.group("hours"))
    if hours % 6:
        raise StageConfigurationError("campaign duration must be a multiple of 6 hours")
    return hours


def load_campaign_spec(config_path: Path) -> CampaignSpec:
    """Load a small campaign YAML and resolve profile/environment references."""
    config_path = config_path.resolve()
    document = _expand_env(_load_mapping(config_path, "campaign"), label="campaign")
    campaign = document.get("campaign")
    if not isinstance(campaign, dict):
        raise StageConfigurationError("campaign YAML must define a campaign mapping")

    name = _required_string(campaign, "name", "campaign")
    start_cycle = _iso(_parse_cycle(_required_string(campaign, "start", "campaign")))

    duration_value = campaign.get("duration")
    end_value = campaign.get("end")
    if duration_value is None and end_value is None:
        raise StageConfigurationError("campaign must define duration or end")

    start = _parse_cycle(start_cycle)
    duration_hours: int
    if duration_value is not None:
        if not isinstance(duration_value, str):
            raise StageConfigurationError("campaign.duration must be a string such as PT72H")
        duration_hours = _parse_duration(duration_value)
        calculated_end = start + timedelta(hours=duration_hours)
    else:
        calculated_end = _parse_cycle(str(end_value))
        duration_hours = int((calculated_end - start).total_seconds() // 3600)
        if duration_hours < 0 or duration_hours % 6:
            raise StageConfigurationError("campaign end must be on or after start and aligned to 6 hours")

    if end_value is not None:
        declared_end = _parse_cycle(str(end_value))
        if declared_end != calculated_end:
            raise StageConfigurationError("campaign.end does not match campaign.duration")
    end_cycle = _iso(calculated_end)

    destination_text = _required_string(campaign, "destination", "campaign")
    destination = _resolve_path(destination_text, config_path.parent)

    profile, profile_dir = _profile(document, config_path.parent)
    initial_jedi_case = _resolve_path(
        _required_string(profile, "initial_jedi_case", "profile"), profile_dir
    )
    cycling_jedi_case = _resolve_path(
        _required_string(profile, "cycling_jedi_case", "profile"), profile_dir
    )
    mpas_case = _resolve_path(_required_string(profile, "mpas_case", "profile"), profile_dir)
    obs2ioda_config = _resolve_path(
        _required_string(profile, "obs2ioda_config", "profile"), profile_dir
    )

    execution = document.get("execution", {})
    if not isinstance(execution, dict):
        raise StageConfigurationError("execution must be a mapping")
    swf_raw = execution.get("swf_command", "swf")
    if isinstance(swf_raw, str):
        swf_command = tuple(shlex.split(swf_raw))
    elif isinstance(swf_raw, list) and all(isinstance(item, str) for item in swf_raw):
        swf_command = tuple(swf_raw)
    else:
        raise StageConfigurationError("execution.swf_command must be a string or list of strings")
    if not swf_command:
        raise StageConfigurationError("execution.swf_command cannot be empty")

    # Reuse the campaign generator's strict horizon validation now, before any work.
    _cycles(start_cycle, end_cycle)

    return CampaignSpec(
        config_path=config_path,
        name=name,
        start_cycle=start_cycle,
        end_cycle=end_cycle,
        duration_hours=duration_hours,
        destination=destination,
        initial_jedi_case=initial_jedi_case,
        cycling_jedi_case=cycling_jedi_case,
        mpas_case=mpas_case,
        obs2ioda_config=obs2ioda_config,
        swf_command=swf_command,
    )


def _command_available(command: str) -> bool:
    path = Path(command).expanduser()
    if path.is_absolute() or "/" in command:
        return path.is_file() and os.access(path, os.X_OK)
    return shutil.which(command) is not None


def _rendered_obs_inputs(config: Path, cycle: datetime) -> tuple[list[Path], list[str]]:
    run = load_obs2ioda_run(config.parent, _iso(cycle)) if config.name == "obs2ioda.yaml" else None
    if run is None:
        # The stage loader expects CONFIG_DIR/obs2ioda.yaml.  Profiles may point to
        # a differently named source file, so make that limitation explicit.
        return [], [f"Obs2IODA profile must currently point to a file named obs2ioda.yaml: {config}"]
    try:
        plan = _build_plan(run)
    except Exception as exc:  # converted to one preflight finding below
        return [], [str(exc)]
    inputs: list[Path] = []
    tools: list[str] = []
    for converter in plan.get("converters", []):
        if not isinstance(converter, dict):
            continue
        for value in converter.get("inputs", []):
            inputs.append(Path(str(value)))
        argv = converter.get("argv", [])
        if isinstance(argv, list) and argv:
            tools.append(str(argv[0]))
    runtime = plan.get("runtime", {})
    if isinstance(runtime, dict):
        for value in runtime.get("dependency_checks", []):
            tools.append(str(value))
        linker = runtime.get("linker_command")
        if linker:
            tools.append(str(linker))
    return inputs, tools


def preflight_campaign(spec: CampaignSpec, *, require_swf: bool = True) -> PreflightReport:
    """Check everything knowable before creating or submitting the campaign."""
    items: list[PreflightItem] = []

    for label, path, kind in (
        ("initial JEDI case", spec.initial_jedi_case, "dir"),
        ("cycling JEDI case", spec.cycling_jedi_case, "dir"),
        ("MPAS case", spec.mpas_case, "dir"),
        ("Obs2IODA configuration", spec.obs2ioda_config, "file"),
    ):
        ok = path.is_dir() if kind == "dir" else path.is_file()
        items.append(PreflightItem(label, ok, str(path)))

    if all(item.ok for item in items[:4]):
        try:
            inputs = _initial_inputs(spec.initial_jedi_case)
            missing_initial = [str(path) for path in inputs.values() if not path.is_file()]
            items.append(
                PreflightItem(
                    "first-cycle starting inputs",
                    not missing_initial,
                    "available" if not missing_initial else ", ".join(missing_initial),
                )
            )
        except Exception as exc:
            items.append(PreflightItem("first-cycle starting inputs", False, str(exc)))

    if require_swf:
        items.append(
            PreflightItem(
                "simpleWorkflow command",
                _command_available(spec.swf_command[0]),
                " ".join(spec.swf_command),
            )
        )
    items.append(
        PreflightItem(
            "MONAN-JEDI command",
            _command_available("monan-jedi-workflow"),
            "monan-jedi-workflow",
        )
    )

    cycles = _cycles(spec.start_cycle, spec.end_cycle)
    obs_cycles = cycles[1:]
    missing_obs: list[str] = []
    missing_tools: set[str] = set()
    if spec.obs2ioda_config.is_file():
        for cycle in obs_cycles:
            inputs, tools = _rendered_obs_inputs(spec.obs2ioda_config, cycle)
            missing_obs.extend(str(path) for path in inputs if not path.is_file())
            missing_tools.update(tool for tool in tools if not _command_available(tool))
    items.append(
        PreflightItem(
            f"observation inputs ({len(obs_cycles)} cycles)",
            not missing_obs,
            "all available" if not missing_obs else "; ".join(sorted(set(missing_obs))),
        )
    )
    items.append(
        PreflightItem(
            "Obs2IODA tools",
            not missing_tools,
            "available" if not missing_tools else ", ".join(sorted(missing_tools)),
        )
    )

    if spec.destination.exists():
        workflow = spec.destination / "workflow.yaml"
        request = spec.destination / "campaign-request.yaml"
        ok = spec.destination.is_dir() and workflow.is_file() and request.is_file()
        detail = "existing restartable campaign" if ok else "destination exists but is not a complete campaign"
        items.append(PreflightItem("destination", ok, detail))
    else:
        parent = spec.destination.parent
        ok = parent.exists() and os.access(parent, os.W_OK)
        items.append(PreflightItem("destination", ok, str(spec.destination)))

    return PreflightReport(spec=spec, items=tuple(items))


def _request_document(spec: CampaignSpec) -> dict[str, Any]:
    return {
        "campaign": {
            "name": spec.name,
            "start": spec.start_cycle,
            "end": spec.end_cycle,
            "duration_hours": spec.duration_hours,
            "destination": str(spec.destination),
        },
        "profile": {
            "initial_jedi_case": str(spec.initial_jedi_case),
            "cycling_jedi_case": str(spec.cycling_jedi_case),
            "mpas_case": str(spec.mpas_case),
            "obs2ioda_config": str(spec.obs2ioda_config),
        },
        "execution": {"swf_command": list(spec.swf_command)},
    }


def _validate_existing_campaign(spec: CampaignSpec) -> None:
    request_path = spec.destination / "campaign-request.yaml"
    if not request_path.is_file():
        raise StageConfigurationError(
            f"destination exists but has no campaign-request.yaml: {spec.destination}"
        )
    existing = _load_mapping(request_path, "materialized campaign request")
    if existing != _request_document(spec):
        raise StageConfigurationError(
            "destination belongs to a different campaign request; use a new destination"
        )
    if not spec.workflow_path.is_file():
        raise StageConfigurationError(
            f"materialized campaign is missing workflow.yaml: {spec.workflow_path}"
        )


def materialize_campaign(spec: CampaignSpec) -> Path:
    """Create the campaign once, or verify an existing restartable campaign."""
    if spec.destination.exists():
        _validate_existing_campaign(spec)
        return spec.destination

    materialize_corrected_campaign(
        initial_jedi_case=spec.initial_jedi_case,
        cycling_jedi_case=spec.cycling_jedi_case,
        mpas_case=spec.mpas_case,
        obs2ioda_config=spec.obs2ioda_config,
        start_cycle=spec.start_cycle,
        end_cycle=spec.end_cycle,
        destination=spec.destination,
    )
    (spec.destination / "campaign-request.yaml").write_text(
        yaml.safe_dump(_request_document(spec), sort_keys=False), encoding="utf-8"
    )
    return spec.destination


def print_preflight(report: PreflightReport) -> None:
    spec = report.spec
    cycles = _cycles(spec.start_cycle, spec.end_cycle)
    print("MONAN-JEDI Campaign")
    print()
    print(f"Name       {spec.name}")
    print(f"Period     {spec.start_cycle} -> {spec.end_cycle}")
    print(f"Duration   {spec.duration_hours} h")
    print(f"Analyses   {len(cycles)}")
    print(f"Forecasts  {max(0, len(cycles) - 1)} x 6 h")
    print(f"Directory  {spec.destination}")
    print()
    print("Preflight")
    for item in report.items:
        marker = "OK" if item.ok else "FAIL"
        print(f"  [{marker:<4}] {item.label}: {item.detail}")
    print()
    print("Preflight PASS" if report.valid else "Preflight FAILED - campaign was not started")


def check_campaign(config_path: Path, *, require_swf: bool = True) -> PreflightReport:
    spec = load_campaign_spec(config_path)
    report = preflight_campaign(spec, require_swf=require_swf)
    print_preflight(report)
    return report


def create_campaign(config_path: Path) -> Path:
    spec = load_campaign_spec(config_path)
    report = preflight_campaign(spec)
    print_preflight(report)
    if not report.valid:
        raise StageConfigurationError("campaign preflight failed")
    path = materialize_campaign(spec)
    print(f"[OK] campaign ready: {path}")
    return path


def _swf(spec: CampaignSpec, action: str) -> int:
    command = [
        *spec.swf_command,
        action,
        str(spec.workflow_path),
        "--workdir",
        str(spec.workdir),
    ]
    return subprocess.run(command, check=False).returncode


def run_campaign(config_path: Path) -> int:
    """Preflight, materialize if needed, then execute or resume the campaign."""
    spec = load_campaign_spec(config_path)
    report = preflight_campaign(spec)
    print_preflight(report)
    if not report.valid:
        return 2
    materialize_campaign(spec)
    print(f"Starting campaign with simpleWorkflow: {spec.workflow_path}")
    return _swf(spec, "run")


def status_campaign(config_path: Path) -> int:
    spec = load_campaign_spec(config_path)
    _validate_existing_campaign(spec)
    return _swf(spec, "status")


def tui_campaign(config_path: Path) -> int:
    spec = load_campaign_spec(config_path)
    _validate_existing_campaign(spec)
    return _swf(spec, "tui")
