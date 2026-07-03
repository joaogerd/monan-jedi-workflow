"""Configurable, safe input providers for MPAS workflow stages.

Providers separate source resolution from scientific conversion.  A provider only
obtains or validates a declared artifact; WPS/UNGRIB and MPAS remain independent
stages.
"""
from __future__ import annotations

import shutil
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .cycle_context import CycleContext, parse_cycle_time
from .provenance import file_record, write_json_atomic
from .yaml_utils import load_yaml_file

_REMOTE_PROVIDERS = {"gfs", "reanalysis", "http"}
_LOCAL_PROVIDERS = {"local", "infrastructure"}
_SUPPORTED_PROVIDERS = _REMOTE_PROVIDERS | _LOCAL_PROVIDERS
_GRIB_FORMATS = {"grib", "grib1", "grib2", "grb", "grb2"}


class InputSourceError(ValueError):
    """The declarative input-provider contract is invalid."""


class InputValidationError(RuntimeError):
    """A declared source cannot safely be used by a downstream stage."""


@dataclass(frozen=True)
class InputSource:
    """Resolved input source for one analysis or initialization cycle."""

    name: str
    provider: str
    target: Path
    url: str | None
    data_format: str
    metadata: dict[str, Any]
    cycle: CycleContext

    @property
    def requires_wps(self) -> bool:
        return self.data_format.lower() in _GRIB_FORMATS


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputSourceError(f"{label} must be a mapping.")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise InputSourceError(f"{label} must be a non-empty string.")
    return value


def _render(value: str, context: dict[str, str], label: str) -> str:
    try:
        return _string(value, label).format(**context)
    except KeyError as error:
        raise InputSourceError(f"{label} uses an unknown placeholder: {error.args[0]!r}") from error


def _resolve(value: str, config_dir: Path, context: dict[str, str], label: str) -> Path:
    path = Path(_render(value, context, label))
    return path if path.is_absolute() else config_dir / path


def _parse_time(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise InputSourceError(f"{label} must include a UTC offset or trailing Z.")
        return value
    try:
        return parse_cycle_time(_string(value, label)).value
    except Exception as error:
        raise InputSourceError(f"{label} must be a timezone-aware ISO-8601 time.") from error


def load_input_sources(config_dir: Path) -> dict[str, dict[str, Any]]:
    """Load ``inputs.yaml`` and validate the shallow provider catalog shape."""
    document = load_yaml_file(config_dir.resolve() / "inputs.yaml")
    root = _mapping(document.get("inputs"), "inputs.yaml.inputs")
    sources = _mapping(root.get("sources"), "inputs.sources")
    if not sources:
        raise InputSourceError("inputs.sources cannot be empty.")
    return sources


def resolve_input_source(config_dir: Path, name: str, cycle_time: str) -> InputSource:
    """Resolve one source without touching the network or filesystem product."""
    config_dir = config_dir.resolve()
    sources = load_input_sources(config_dir)
    if name not in sources:
        available = ", ".join(sorted(sources))
        raise InputSourceError(f"Unknown input source {name!r}. Available sources: {available}")
    spec = _mapping(sources[name], f"inputs.sources.{name}")
    provider = _string(spec.get("provider"), f"inputs.sources.{name}.provider").lower()
    if provider not in _SUPPORTED_PROVIDERS:
        raise InputSourceError(
            f"inputs.sources.{name}.provider must be one of {sorted(_SUPPORTED_PROVIDERS)}."
        )
    cycle = parse_cycle_time(cycle_time)
    context = cycle.render_context()
    target = _resolve(spec.get("target"), config_dir, context, f"inputs.sources.{name}.target")
    url: str | None = None
    if provider in _REMOTE_PROVIDERS:
        url = _render(spec.get("url"), context, f"inputs.sources.{name}.url")
    elif "url" in spec:
        raise InputSourceError(f"inputs.sources.{name}.url is only valid for remote providers.")
    data_format = _string(spec.get("format", "unknown"), f"inputs.sources.{name}.format")
    return InputSource(name, provider, target, url, data_format, spec, cycle)


def _validate_coverage(source: InputSource) -> None:
    coverage = source.metadata.get("coverage")
    if coverage is None:
        return
    coverage = _mapping(coverage, f"inputs.sources.{source.name}.coverage")
    start = _parse_time(coverage.get("start"), "coverage.start")
    end = _parse_time(coverage.get("end"), "coverage.end")
    if end < start:
        raise InputSourceError(f"inputs.sources.{source.name}.coverage has end before start.")
    if not start <= source.cycle.value <= end:
        raise InputValidationError(
            f"Source {source.name!r} covers {start.isoformat()} to {end.isoformat()}, "
            f"not requested cycle {source.cycle.cycle_time}."
        )


def validate_input_source(
    source: InputSource,
    *,
    required_mesh: str | None = None,
    with_checksum: bool = False,
) -> dict[str, Any]:
    """Validate declared coverage, mesh metadata, format, integrity and checksum."""
    _validate_coverage(source)
    expected_mesh = source.metadata.get("mesh")
    if required_mesh and expected_mesh and expected_mesh != required_mesh:
        raise InputValidationError(
            f"Source {source.name!r} declares mesh {expected_mesh!r}, expected {required_mesh!r}."
        )
    if not source.target.is_file():
        raise InputValidationError(f"Input source product is missing: {source.target}")
    min_bytes = int(source.metadata.get("min_bytes", 1))
    if min_bytes < 1:
        raise InputSourceError(f"inputs.sources.{source.name}.min_bytes must be at least 1.")
    if source.target.stat().st_size < min_bytes:
        raise InputValidationError(
            f"Input source product is smaller than declared minimum ({min_bytes} bytes): {source.target}"
        )
    suffixes = source.metadata.get("suffixes")
    if suffixes is not None:
        if not isinstance(suffixes, list) or not all(isinstance(item, str) and item for item in suffixes):
            raise InputSourceError(f"inputs.sources.{source.name}.suffixes must be a list of non-empty strings.")
        if source.target.suffix.lower() not in {item.lower() for item in suffixes}:
            raise InputValidationError(
                f"Input source {source.target} does not match allowed suffixes: {', '.join(suffixes)}"
            )
    expected_sha = source.metadata.get("sha256")
    record = file_record(source.target, with_checksum=with_checksum or bool(expected_sha))
    if expected_sha and record.get("sha256") != expected_sha:
        raise InputValidationError(f"Checksum mismatch for input source: {source.target}")
    return {
        "source": source.name,
        "provider": source.provider,
        "format": source.data_format,
        "requires_wps": source.requires_wps,
        "cycle_time": source.cycle.cycle_time,
        "mesh": expected_mesh,
        "product": record,
    }


def fetch_input_source(source: InputSource, *, overwrite: bool = False) -> Path:
    """Explicitly retrieve a remote source, never replacing a valid product by default."""
    if source.provider in _LOCAL_PROVIDERS:
        if source.target.is_file():
            return source.target
        raise InputValidationError(
            f"Provider {source.provider!r} is local and cannot fetch a missing product: {source.target}"
        )
    if source.url is None:
        raise InputSourceError(f"Remote source {source.name!r} has no resolved URL.")
    if source.target.exists() and not overwrite:
        raise FileExistsError(
            f"Refusing to overwrite existing input product without --overwrite: {source.target}"
        )
    source.target.parent.mkdir(parents=True, exist_ok=True)
    temporary = source.target.with_name(f".{source.target.name}.part")
    try:
        with urllib.request.urlopen(source.url) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(source.target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return source.target


def write_input_report(config_dir: Path, source: InputSource, report: dict[str, Any]) -> Path:
    """Persist source provenance beside workflow state for reproducible resumes."""
    state_dir = config_dir.resolve() / ".monan-jedi-workflow" / source.cycle.cycle_id
    return write_json_atomic(state_dir / f"input-{source.name}.json", report)
