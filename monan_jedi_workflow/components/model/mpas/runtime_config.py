"""Reusable compiler for MPAS command runtime configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ....platforms.base import ExecutionBackend, ExecutionRequest
from .output_validation import MpasOutputContract
from .staging import LinkSpec, TemplateSpec


class MpasRuntimeConfigurationError(ValueError):
    """Raised when a generic MPAS runtime declaration is invalid."""


@dataclass(frozen=True)
class CompiledMpasRuntime:
    """Executable MPAS runtime assembled from resolved configuration.

    Parameters
    ----------
    run_dir : Path
        Rendered run directory.
    request : ExecutionRequest
        Explicit executable request.
    contract : MpasOutputContract
        Additional output and log validation contract.
    links : tuple[LinkSpec, ...]
        Staged links.
    templates : tuple[TemplateSpec, ...]
        Rendered templates.
    values : Mapping[str, object]
        Fully rendered context shared by staging and command execution.
    """

    run_dir: Path
    request: ExecutionRequest
    contract: MpasOutputContract
    links: tuple[LinkSpec, ...]
    templates: tuple[TemplateSpec, ...]
    values: Mapping[str, object]


def require_mapping(value: object, label: str) -> Mapping[str, object]:
    """Return a mapping or raise a contextual configuration error."""
    if not isinstance(value, Mapping):
        raise MpasRuntimeConfigurationError(f"{label} must be a mapping.")
    return value


def _render(value: str, values: Mapping[str, object], label: str) -> str:
    """Render one format string and report unknown placeholders clearly."""
    try:
        return value.format_map(values)
    except KeyError as exc:
        raise MpasRuntimeConfigurationError(f"{label} uses unknown placeholder: {exc.args[0]}") from exc


def _compile_staging(
    raw: object,
    label: str,
    values: Mapping[str, object],
    workspace: Path,
    run_dir: Path,
    kind: type[LinkSpec] | type[TemplateSpec],
) -> tuple[LinkSpec, ...] | tuple[TemplateSpec, ...]:
    """Compile declared links or templates using explicit source/target rules."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise MpasRuntimeConfigurationError(f"{label} must be a list.")
    compiled = []
    for index, item in enumerate(raw):
        entry = require_mapping(item, f"{label}[{index}]")
        source, target = entry.get("source"), entry.get("target")
        if not isinstance(source, str) or not source or not isinstance(target, str) or not target:
            raise MpasRuntimeConfigurationError(f"{label}[{index}] requires non-empty source and target.")
        source_path = Path(_render(source, values, f"{label}[{index}].source"))
        target_path = Path(_render(target, values, f"{label}[{index}].target"))
        compiled.append(kind(source_path if source_path.is_absolute() else workspace / source_path, target_path if target_path.is_absolute() else run_dir / target_path))
    return tuple(compiled)


def compile_runtime(
    section: Mapping[str, object],
    *,
    label: str,
    workspace: Path,
    values: Mapping[str, object],
    backend: ExecutionBackend,
) -> CompiledMpasRuntime:
    """Compile common MPAS runtime settings into explicit execution contracts.

    Parameters
    ----------
    section : Mapping[str, object]
        Runtime configuration containing `run_dir`, `argv`, optional environment,
        staging, and validation settings.
    label : str
        Configuration path used in validation errors.
    workspace : Path
        Explicit workflow workspace.
    values : Mapping[str, object]
        Product-specific template context.
    backend : ExecutionBackend
        Selected execution backend.

    Returns
    -------
    CompiledMpasRuntime
        Rendered runtime request and staging contract.
    """
    run_template, argv = section.get("run_dir"), section.get("argv")
    if not isinstance(run_template, str) or not run_template:
        raise MpasRuntimeConfigurationError(f"{label}.run_dir must be a non-empty string.")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise MpasRuntimeConfigurationError(f"{label}.argv must be a non-empty string list.")
    rendered = dict(values)
    candidate = Path(_render(run_template, rendered, f"{label}.run_dir"))
    run_dir = candidate if candidate.is_absolute() else workspace / candidate
    rendered["run_dir"] = str(run_dir)
    command = tuple(_render(item, rendered, f"{label}.argv") for item in argv)

    environment = section.get("environment", {})
    if not isinstance(environment, Mapping) or not all(isinstance(key, str) and isinstance(value, str) for key, value in environment.items()):
        raise MpasRuntimeConfigurationError(f"{label}.environment must map strings to strings.")
    rendered_environment = {key: _render(value, rendered, f"{label}.environment.{key}") for key, value in environment.items()}

    validation = require_mapping(section.get("validation", {}), f"{label}.validation")
    outputs = validation.get("required_outputs", [])
    markers = validation.get("required_log_markers", [])
    log = validation.get("log")
    if not isinstance(outputs, list) or not isinstance(markers, list) or not all(isinstance(item, str) and item for item in [*outputs, *markers]):
        raise MpasRuntimeConfigurationError(f"{label}.validation outputs and markers must be string lists.")
    if log is not None and not isinstance(log, str):
        raise MpasRuntimeConfigurationError(f"{label}.validation.log must be a string.")

    links = _compile_staging(section.get("links"), f"{label}.links", rendered, workspace, run_dir, LinkSpec)
    templates = _compile_staging(section.get("templates"), f"{label}.templates", rendered, workspace, run_dir, TemplateSpec)
    request = ExecutionRequest(command, run_dir, rendered_environment, run_dir / "stdout.log", run_dir / "stderr.log")
    contract = MpasOutputContract(
        tuple(Path(_render(item, rendered, f"{label}.validation.required_outputs")) for item in outputs),
        Path(_render(log, rendered, f"{label}.validation.log")) if log else None,
        tuple(markers),
    )
    return CompiledMpasRuntime(run_dir, request, contract, links, templates, rendered)
