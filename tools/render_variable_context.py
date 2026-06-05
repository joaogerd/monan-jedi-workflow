#!/usr/bin/env python3
"""Render a MONAN/JEDI variable context from an explicit variable map.

This tool converts a named variable mapping profile into the compact `jedi`
fragment consumed by the 3DVar-FGAT template renderer.  It keeps conceptual
JEDI names, MPAS/NetCDF names and SABER/BUMP names separated in the source
mapping file. Profiles may render canonical JEDI names for the final YAML while
retaining MPAS/internal aliases for validation and provenance.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import yaml


def _expand(value: Any) -> Any:
    """Recursively expand environment variables in strings."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a YAML mapping at top level")
    return data


def _resolve_ordered(
    order: list[str],
    mapping: dict[str, str],
    direct: list[str] | None = None,
    *,
    render_name_mode: str = "mapped",
) -> list[str]:
    direct_set = set(direct or [])
    resolved: list[str] = []
    missing: list[str] = []
    for name in order:
        if name in mapping:
            resolved.append(name if render_name_mode == "canonical" else mapping[name])
        elif name in direct_set:
            resolved.append(name)
        elif render_name_mode == "canonical":
            resolved.append(name)
        else:
            missing.append(name)
    if missing:
        raise KeyError("unresolved variable(s): " + ", ".join(missing))
    return resolved

def _inline_list(values: list[str]) -> str:
    return ", ".join(values)


def _render_vertical_balance_yaml(entries: list[dict[str, Any]], indent: int = 12) -> str:
    prefix = " " * indent
    lines: list[str] = []

    for entry in entries:
        lines.append(f"{prefix}- balanced variable: {entry['balanced_variable']}")
        lines.append(f"{prefix}  unbalanced variable: {entry['unbalanced_variable']}")

        if "diagonal_regression" in entry:
            value = str(entry["diagonal_regression"]).lower()
            lines.append(f"{prefix}  diagonal regression: {value}")

    return "\n".join(lines)


def render_context(variable_map: dict[str, Any], profile_name: str | None) -> dict[str, Any]:
    if not profile_name:
        profile_name = variable_map.get("default_profile")
    if not profile_name:
        raise KeyError("No profile was provided and default_profile is missing")

    profiles = variable_map.get("profiles") or {}
    if profile_name not in profiles:
        available = ", ".join(sorted(profiles))
        raise KeyError(f"Unknown variable profile '{profile_name}'. Available: {available}")

    profile = profiles[profile_name]
    render_name_mode = profile.get("render_name_mode", "mapped")
    if render_name_mode not in {"mapped", "canonical"}:
        raise ValueError(
            "render_name_mode must be either 'mapped' or 'canonical', "
            f"got {render_name_mode!r}"
        )

    analysis = profile.get("analysis_variables", {})
    state = profile.get("state_variables", {})
    saber = profile.get("saber_bump", {})
    control = saber.get("control_variables", {})

    analysis_variables = _resolve_ordered(
        list(analysis.get("order", [])),
        dict(analysis.get("canonical_to_model", {})),
        render_name_mode=render_name_mode,
    )

    state_variables = _resolve_ordered(
        list(state.get("order", [])),
        dict(state.get("canonical_to_model", {})),
        list(state.get("direct_model", [])),
        render_name_mode=render_name_mode,
    )

    bump_control_variables = _resolve_ordered(
        list(control.get("order", [])),
        dict(control.get("canonical_to_bump", {})),
    )

    bump_3d_variables = list(saber.get("variables_3d", []))
    bump_2d_variables = list(saber.get("variables_2d", []))
    vertical_balance = list(saber.get("vertical_balance", []))
    prefixes = saber.get("file_prefixes", {}) or {}

    resolved = {
        "analysis_variables": analysis_variables,
        "state_variables": state_variables,
        "model_variables": state_variables,
        "bump_cov_control_variables": bump_control_variables,
        "bump_3d_control_variables": bump_3d_variables,
        "bump_2d_control_variables": bump_2d_variables,
        "bump_vertical_balance": vertical_balance,
        "bump_cov_prefix": prefixes.get("nicas", "mpas"),
        "bump_cov_vbal_prefix": prefixes.get("vbal", "mpas"),
        "linear_variable_change_name": profile.get(
            "linear_variable_change_name",
            "Control2Analysis",
        ),
        "deallocate_non_da_fields": str(
            profile.get("deallocate_non_da_fields", False)
        ).lower(),
    }

    template_context = dict(resolved)
    template_context.update(
        {
            "analysis_variables": _inline_list(analysis_variables),
            "state_variables": _inline_list(state_variables),
            "model_variables": _inline_list(state_variables),
            "bump_cov_control_variables": _inline_list(bump_control_variables),
            "bump_3d_control_variables": _inline_list(bump_3d_variables),
            "bump_2d_control_variables": _inline_list(bump_2d_variables),
            "bump_vertical_balance_yaml": _render_vertical_balance_yaml(
                vertical_balance
            ),
        }
    )

    return {
        "variable_profile": profile_name,
        "jedi": template_context,
        "resolved": resolved,
        "provenance": {
            "variable_profile": profile_name,
            "profile_description": profile.get("description", ""),
            "render_name_mode": render_name_mode,
            "analysis_canonical_to_model": analysis.get("canonical_to_model", {}),
            "state_canonical_to_model": state.get("canonical_to_model", {}),
            "state_direct_model": state.get("direct_model", []),
            "bump_canonical_to_bump": control.get("canonical_to_bump", {}),
        },
    }


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(data, stream, sort_keys=False, default_flow_style=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, type=Path, help="Variable map YAML file")
    parser.add_argument("--profile", default=None, help="Profile name to render")
    parser.add_argument("--output", required=True, type=Path, help="Output YAML context")
    parser.add_argument(
        "--trace",
        type=Path,
        default=None,
        help="Optional provenance trace YAML output",
    )
    args = parser.parse_args()

    variable_map = _expand(_load_yaml(args.map))
    context = render_context(variable_map, args.profile)
    write_yaml(args.output, {"jedi": context["jedi"]})

    if args.trace:
        write_yaml(
            args.trace,
            {
                "stage": "variable_context",
                "status": "completed",
                "variable_map": str(args.map),
                "output": str(args.output),
                **context["provenance"],
                "resolved": context["resolved"],
            },
        )

    print(f"[INFO] Variable profile: {context['variable_profile']}")
    print(f"[INFO] Variable context written to {args.output}")
    if args.trace:
        print(f"[INFO] Variable trace written to {args.trace}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
