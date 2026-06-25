"""Helpers for optional cycle-aware MPAS and Obs2IODA stage files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .cycle_context import CycleContext
from .yaml_utils import load_yaml_file


class StageConfigurationError(ValueError):
    """An optional domain-stage YAML contract is incomplete or invalid."""


def load_stage_config(config_dir: Path, filename: str, root_key: str) -> dict[str, Any]:
    """Load one optional-stage mapping and return its named root section."""
    path = config_dir.resolve() / filename
    data = load_yaml_file(path)
    section = data.get(root_key)
    if not isinstance(section, dict):
        raise StageConfigurationError(f"{filename} must define a mapping named '{root_key}'.")
    return section


def render_text(value: str, context: dict[str, str], *, label: str) -> str:
    """Render a declared path or command argument without shell evaluation."""
    if not isinstance(value, str) or not value:
        raise StageConfigurationError(f"{label} must be a non-empty string.")
    try:
        return value.format(**context)
    except KeyError as error:
        raise StageConfigurationError(
            f"{label} uses an unknown placeholder: {error.args[0]!r}"
        ) from error


def render_declared_variables(
    section: dict[str, Any],
    context: dict[str, str],
    *,
    label: str,
) -> dict[str, str]:
    """Extend a cycle context with ordered, string-only YAML variables.

    Variables are rendered in declaration order. A variable may reference the
    standard cycle fields and variables declared above it, but it may not
    replace a standard field such as ``cycle_id`` or ``work_dir``.
    """
    variables = section.get("variables", {})
    if variables is None:
        variables = {}
    if not isinstance(variables, dict):
        raise StageConfigurationError(f"{label}.variables must be a mapping.")

    rendered = dict(context)
    for name, value in variables.items():
        if not isinstance(name, str) or not name:
            raise StageConfigurationError(f"{label}.variables keys must be non-empty strings.")
        if name in rendered:
            raise StageConfigurationError(
                f"{label}.variables may not replace reserved context field {name!r}."
            )
        rendered[name] = render_text(value, rendered, label=f"{label}.variables.{name}")
    return rendered


def resolve_path(value: str, *, config_dir: Path, context: dict[str, str], label: str) -> Path:
    """Render a path and resolve relative paths from the experiment directory."""
    rendered = Path(render_text(value, context, label=label))
    return rendered if rendered.is_absolute() else config_dir.resolve() / rendered


def cycle_render_context(cycle: CycleContext, *, lead_hours: int = 0) -> dict[str, str]:
    """Return standard template values for a stage configuration."""
    return cycle.render_context(lead_hours=lead_hours)
