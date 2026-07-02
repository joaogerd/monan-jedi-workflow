"""Idempotent file staging utilities for MPAS run directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class MpasStagingError(RuntimeError):
    """Raised when MPAS staging would overwrite or render an unsafe target."""


@dataclass(frozen=True)
class LinkSpec:
    """Declare one source file and its run-directory target."""

    source: Path
    target: Path


@dataclass(frozen=True)
class TemplateSpec:
    """Declare one UTF-8 template and its rendered target."""

    source: Path
    target: Path


def stage_link(spec: LinkSpec) -> Path:
    """Create an idempotent symbolic link.

    Existing matching links are reused. A regular file is never overwritten
    because it may be a scientific artifact from a previous run.
    """
    if not spec.source.exists():
        raise MpasStagingError(f"MPAS staging source is missing: {spec.source}")
    spec.target.parent.mkdir(parents=True, exist_ok=True)
    if spec.target.is_symlink():
        if spec.target.resolve() == spec.source.resolve():
            return spec.target
        spec.target.unlink()
    elif spec.target.exists():
        raise MpasStagingError(f"MPAS staging refuses to overwrite a regular target: {spec.target}")
    spec.target.symlink_to(spec.source)
    return spec.target


def render_template(spec: TemplateSpec, context: Mapping[str, object]) -> Path:
    """Render a template with an explicit context mapping.

    Unknown placeholders fail early instead of leaking implicit shell state into
    a forecast run directory.
    """
    if not spec.source.is_file():
        raise MpasStagingError(f"MPAS template is missing: {spec.source}")
    try:
        rendered = spec.source.read_text(encoding="utf-8").format_map(context)
    except KeyError as exc:
        raise MpasStagingError(f"MPAS template uses unknown placeholder: {exc.args[0]}") from exc
    spec.target.parent.mkdir(parents=True, exist_ok=True)
    spec.target.write_text(rendered, encoding="utf-8")
    return spec.target
