"""Acquire cycle-correct observation inputs before a campaign starts."""

from __future__ import annotations

import json
import os
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .campaign import load_campaign_spec
from .corrected_campaign import _cycles, _iso
from .obs2ioda_stage import _build_plan, load_obs2ioda_run
from .obs_cycle_inputs import (
    InputResolution,
    ObservationInputError,
    cycle_candidate,
    find_local_cycle_input,
)
from .stage_config import StageConfigurationError


@dataclass(frozen=True)
class AcquisitionRecord:
    converter: str
    cycle: str
    destination: str
    method: str
    source: str
    size_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise StageConfigurationError(f"YAML root must be a mapping: {path}")
    return data


def _expand(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def _acquisition_config(config_path: Path) -> dict[str, Any]:
    document = _expand(_load_yaml(config_path.resolve()))
    raw_profile = document.get("profile")
    if isinstance(raw_profile, dict):
        profile = raw_profile
        base = config_path.resolve().parent
    elif isinstance(raw_profile, str) and raw_profile:
        profile_path = Path(raw_profile).expanduser()
        if not profile_path.is_absolute():
            profile_path = config_path.resolve().parent / profile_path
        profile_path = profile_path.resolve()
        profile_doc = _expand(_load_yaml(profile_path))
        profile = profile_doc.get("profile", profile_doc)
        base = profile_path.parent
    else:
        raise StageConfigurationError("campaign profile must be a mapping or YAML path")
    if not isinstance(profile, dict):
        raise StageConfigurationError("campaign profile must be a mapping")

    raw = profile.get("observation_acquisition", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise StageConfigurationError("profile.observation_acquisition must be a mapping")
    raw = _expand(raw)
    raw["_base_dir"] = str(base)
    return raw


def _search_roots(config: dict[str, Any]) -> list[Path]:
    values = config.get("search_roots", [])
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise StageConfigurationError("observation_acquisition.search_roots must be a list of paths")
    base = Path(str(config.get("_base_dir", ".")))
    roots: list[Path] = []
    for value in values:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = base / path
        roots.append(path.resolve(strict=False))
    return roots


def _provider_for(config: dict[str, Any], converter: str) -> dict[str, Any] | None:
    providers = config.get("providers", {})
    if not isinstance(providers, dict):
        raise StageConfigurationError("observation_acquisition.providers must be a mapping")
    value = providers.get(converter)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise StageConfigurationError(
            f"observation acquisition provider for {converter!r} must be a mapping"
        )
    return value


def _render(template: str, cycle) -> str:
    if not isinstance(template, str) or not template:
        raise StageConfigurationError("observation acquisition template must be a non-empty string")
    return template.format(**cycle.render_context())


def _download(url: str, destination: Path, *, timeout: int) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "MONAN-JEDI-workflow/0.2"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as stream:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                stream.write(block)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        temporary.unlink(missing_ok=True)
        raise ObservationInputError(
            "Remote observation download failed\n"
            f"  URL: {url}\n"
            f"  Destination: {destination}\n"
            f"  Cause: {error}"
        ) from None
    if not temporary.is_file() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise ObservationInputError(f"Remote observation download was empty: {url}")
    temporary.replace(destination)
    return destination.stat().st_size


def _extract_member(archive: Path, member_name: str, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tar:
        matches = [member for member in tar.getmembers() if Path(member.name).name == member_name]
        if len(matches) != 1:
            raise ObservationInputError(
                "GPSRO archive does not contain exactly one requested cycle member\n"
                f"  Archive: {archive}\n"
                f"  Expected member: {member_name}\n"
                f"  Matches: {len(matches)}"
            )
        member = matches[0]
        source = tar.extractfile(member)
        if source is None:
            raise ObservationInputError(f"Cannot read archive member: {member.name}")
        temporary = destination.with_name(destination.name + ".part")
        temporary.unlink(missing_ok=True)
        with source, temporary.open("wb") as stream:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                stream.write(block)
        if temporary.stat().st_size == 0:
            temporary.unlink(missing_ok=True)
            raise ObservationInputError(f"Extracted observation is empty: {member.name}")
        temporary.replace(destination)
    return destination.stat().st_size


def _write_provenance(destination: Path, record: AcquisitionRecord) -> None:
    sidecar = destination.with_name(destination.name + ".source.json")
    payload = {"acquired_at": _timestamp(), **record.as_dict()}
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _acquire_remote(candidate: Path, cycle, converter: str, provider: dict[str, Any]) -> AcquisitionRecord:
    kind = str(provider.get("type", "https"))
    url = _render(str(provider.get("url", "")), cycle)
    timeout = int(provider.get("timeout_seconds", 180))

    if kind == "https":
        size = _download(url, candidate, timeout=timeout)
        record = AcquisitionRecord(converter, cycle.cycle_time, str(candidate), "https", url, size)
        _write_provenance(candidate, record)
        return record

    if kind == "https-tar":
        member = _render(str(provider.get("member", "")), cycle)
        with tempfile.TemporaryDirectory(prefix="monan-jedi-obs-") as temporary_dir:
            archive = Path(temporary_dir) / Path(url).name
            _download(url, archive, timeout=timeout)
            size = _extract_member(archive, Path(member).name, candidate)
        record = AcquisitionRecord(
            converter,
            cycle.cycle_time,
            str(candidate),
            "https-tar",
            f"{url}#{Path(member).name}",
            size,
        )
        _write_provenance(candidate, record)
        return record

    raise StageConfigurationError(
        f"unsupported observation acquisition provider type for {converter}: {kind}"
    )


def acquire_campaign_observations(config_path: Path) -> list[AcquisitionRecord | InputResolution]:
    """Resolve/fetch every non-initial observation input required by a campaign."""
    spec = load_campaign_spec(config_path)
    config = _acquisition_config(config_path)
    enabled = bool(config.get("enabled", False))
    roots = _search_roots(config) if config else []
    results: list[AcquisitionRecord | InputResolution] = []

    for cycle_dt in _cycles(spec.start_cycle, spec.end_cycle)[1:]:
        cycle_time = _iso(cycle_dt)
        run = load_obs2ioda_run(spec.obs2ioda_config.parent, cycle_time)
        plan = _build_plan(run)
        for raw_converter in plan.get("converters", []):
            if not isinstance(raw_converter, dict):
                continue
            converter = str(raw_converter.get("name", "converter"))
            provider = _provider_for(config, converter) if config else None
            for raw_input in raw_converter.get("inputs", []):
                configured = Path(str(raw_input))
                candidate, changed = cycle_candidate(configured, run.cycle)
                if not changed and candidate.is_file():
                    continue
                found = find_local_cycle_input(candidate, run.cycle, converter, roots)
                if found is not None:
                    if found != configured:
                        results.append(
                            InputResolution(
                                converter=converter,
                                cycle=run.cycle.cycle_time,
                                configured=str(configured),
                                resolved=str(found),
                                method="cycle-pattern" if found == candidate else "local-search",
                            )
                        )
                    continue
                if not enabled or provider is None:
                    raise ObservationInputError(
                        "Observation input is missing and no automatic source is configured\n"
                        f"  Requested cycle: {run.cycle.cycle_time}\n"
                        f"  Converter: {converter}\n"
                        f"  Expected file: {candidate}"
                    )
                results.append(_acquire_remote(candidate, run.cycle, converter, provider))

    return results
