"""Resolve explicit internal references in workflow configuration mappings.

The resolver is intentionally deterministic and side-effect free. It does not
expand environment variables, read files, or evaluate expressions.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


REFERENCE_PATTERN = re.compile(
    r"\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\}"
)

LATE_PLACEHOLDERS = frozenset(
    {
        "cycle_id",
        "analysis_time",
        "analysis_mpas_time",
        "forecast_start_time",
        "forecast_start_mpas_time",
        "valid_time",
        "valid_mpas_time",
        "offset_hours",
        "forecast_lead_hours",
    }
)

REFERENCE_ALIASES = {
    "tasks": "run.tasks",
    "experiment_name": "experiment.name",
}


class ReferenceResolutionError(ValueError):
    """Base error raised for invalid configuration references."""


class UnknownReferenceError(ReferenceResolutionError):
    """Raised when a reference does not exist in the configuration."""


class CircularReferenceError(ReferenceResolutionError):
    """Raised when references form a cycle."""


def _path_value(root: dict[str, Any], path: str) -> Any:
    value: Any = root
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise UnknownReferenceError(f"Unknown configuration reference: {{{path}}}")
        value = value[key]
    return value


def _display_path(path: str) -> str:
    return f"{{{path}}}"


def resolve_references(
    configuration: dict[str, Any],
    *,
    late_placeholders: frozenset[str] = LATE_PLACEHOLDERS,
    aliases: dict[str, str] = REFERENCE_ALIASES,
) -> dict[str, Any]:
    """Resolve internal ``{path.to.value}`` references in a configuration.

    Entire-string references retain the referenced value's type. Embedded
    references require scalar values and are rendered as text. Approved late
    placeholders are preserved verbatim for the cycle renderer.

    The resolver only reads the supplied mapping. In particular, it never
    expands ``$VARIABLE`` or ``~`` forms.
    """
    if not isinstance(configuration, dict):
        raise TypeError("Configuration must be a mapping.")

    raw = deepcopy(configuration)
    cache: dict[str, Any] = {}
    stack: list[str] = []

    def canonical_path(path: str) -> str:
        return aliases.get(path, path)

    def resolve_path(path: str) -> Any:
        path = canonical_path(path)
        if path in cache:
            return deepcopy(cache[path])
        if path in stack:
            start = stack.index(path)
            chain = stack[start:] + [path]
            rendered = " -> ".join(_display_path(item) for item in chain)
            raise CircularReferenceError(f"Circular configuration reference: {rendered}")

        _path_value(raw, path)
        stack.append(path)
        try:
            resolved = resolve_value(_path_value(raw, path))
        finally:
            stack.pop()
        cache[path] = resolved
        return deepcopy(resolved)

    def resolve_text(text: str) -> Any:
        matches = list(REFERENCE_PATTERN.finditer(text))
        if not matches:
            return text

        if len(matches) == 1 and matches[0].span() == (0, len(text)):
            reference = matches[0].group(1)
            if reference in late_placeholders:
                return text
            return resolve_path(reference)

        pieces: list[str] = []
        cursor = 0
        for match in matches:
            pieces.append(text[cursor:match.start()])
            reference = match.group(1)
            if reference in late_placeholders:
                pieces.append(match.group(0))
            else:
                value = resolve_path(reference)
                if isinstance(value, (dict, list)):
                    raise ReferenceResolutionError(
                        f"Embedded reference {_display_path(reference)} must resolve "
                        "to a scalar value."
                    )
                if value is None:
                    raise ReferenceResolutionError(
                        f"Embedded reference {_display_path(reference)} cannot resolve to null."
                    )
                pieces.append(str(value))
            cursor = match.end()
        pieces.append(text[cursor:])
        return "".join(pieces)

    def resolve_value(value: Any) -> Any:
        if isinstance(value, str):
            return resolve_text(value)
        if isinstance(value, list):
            return [resolve_value(item) for item in value]
        if isinstance(value, dict):
            return {key: resolve_value(item) for key, item in value.items()}
        return deepcopy(value)

    return {key: resolve_path(key) for key in raw}
