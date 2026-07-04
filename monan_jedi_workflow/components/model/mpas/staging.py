"""Idempotent file staging utilities for MPAS run directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class MpasStagingError(RuntimeError):
    """Raised when MPAS staging would overwrite or render an unsafe target."""


@dataclass(frozen=True)
class LinkSpec:
    """Declare one source file and its run-directory target.

    Parameters
    ----------
    source : Path
        Input artifact path.
    target : Path
        Link path created under the run directory.
    upstream_artifact : bool, default=False
        Whether ``source`` is produced by a declared upstream workflow stage.
        Preparation-only preflight may create a dangling link for this explicit
        dependency; normal execution still requires the source to exist.
    """

    source: Path
    target: Path
    upstream_artifact: bool = False


@dataclass(frozen=True)
class TemplateSpec:
    """Declare one UTF-8 template and its rendered target."""

    source: Path
    target: Path


def stage_link(spec: LinkSpec, *, allow_missing_source: bool = False) -> Path:
    """Create an idempotent symbolic link.

    Existing matching links are reused. A regular file is never overwritten
    because it may be a scientific artifact from a previous run. Missing source
    files are accepted only for an explicitly declared upstream artifact during
    a preparation-only preflight.
    """
    if not spec.source.exists() and not (allow_missing_source and spec.upstream_artifact):
        raise MpasStagingError(f"MPAS staging source is missing: {spec.source}")
    spec.target.parent.mkdir(parents=True, exist_ok=True)
    if spec.target.is_symlink():
        if spec.target.resolve(strict=False) == spec.source.resolve(strict=False):
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
