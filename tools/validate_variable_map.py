#!/usr/bin/env python3
"""Validate MONAN/JEDI variable-map profiles against staged NetCDF inputs.

The validator is intentionally lightweight. It checks the variable names that
are explicitly resolved by `tools/render_variable_context.py` against the files
that are already staged for the 3DVar-FGAT tutorial case.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


STATUS_OK = 0
STATUS_WARN = 1
STATUS_ERROR = 2


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a YAML mapping")
    return data


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()


def ncdump_variables(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(path)

    result = subprocess.run(
        ["ncdump", "-h", str(path)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    variables: set[str] = set()
    pattern = re.compile(r"^\s*(?:byte|char|short|int|int64|float|double|string)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            variables.add(match.group(1))
    return variables


def resolve_profile(variable_map: dict[str, Any], profile_name: str | None) -> tuple[str, dict[str, Any]]:
    profile_name = profile_name or variable_map.get("default_profile")
    if not profile_name:
        raise KeyError("No profile provided and default_profile is missing")

    profiles = variable_map.get("profiles") or {}
    if profile_name not in profiles:
        raise KeyError(f"Unknown profile: {profile_name}")
    return profile_name, profiles[profile_name]


def resolve_order(order: list[str], mapping: dict[str, str], direct: list[str] | None = None) -> list[str]:
    direct_set = set(direct or [])
    output: list[str] = []
    missing: list[str] = []
    for name in order:
        if name in mapping:
            output.append(mapping[name])
        elif name in direct_set:
            output.append(name)
        else:
            missing.append(name)
    if missing:
        raise KeyError("Unresolved variable(s): " + ", ".join(missing))
    return output


def first_existing_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(directory.glob(pattern))
    return matches[0] if matches else None


def report_check(label: str, required: list[str], available: set[str], strict: bool) -> int:
    missing = [name for name in required if name not in available]
    if not missing:
        print(f"[INFO] {label}: all {len(required)} variable(s) found")
        return STATUS_OK

    message = f"{label}: missing variable(s): {', '.join(missing)}"
    if strict:
        print(f"[ERROR] {message}")
        return STATUS_ERROR

    print(f"[WARN] {message}")
    return STATUS_WARN
    
def report_candidate_check(
    label: str,
    required: list[str],
    available: set[str],
    candidates: dict[str, list[str]],
    strict: bool,
) -> int:
    missing: list[str] = []
    resolved_by_candidate: dict[str, str] = {}

    for name in required:
        candidate_list = candidates.get(name, [name])
        found = next((candidate for candidate in candidate_list if candidate in available), None)

        if found:
            resolved_by_candidate[name] = found
        else:
            missing.append(f"{name} candidates={candidate_list}")

    if not missing:
        print(f"[INFO] {label}: all {len(required)} variable(s) resolved")

        aliased = {
            name: found
            for name, found in resolved_by_candidate.items()
            if name != found
        }

        if aliased:
            aliases = ", ".join(
                f"{name}->{found}"
                for name, found in sorted(aliased.items())
            )
            print(f"[INFO] {label}: aliases used: {aliases}")

        return STATUS_OK

    message = f"{label}: unresolved variable(s): {'; '.join(missing)}"

    if strict:
        print(f"[ERROR] {message}")
        return STATUS_ERROR

    print(f"[WARN] {message}")
    return STATUS_WARN

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, type=Path, help="Variable map YAML file")
    parser.add_argument("--profile", default=None, help="Variable profile name")
    parser.add_argument("--background", required=True, help="MPAS background NetCDF file")
    parser.add_argument("--stddev", required=True, help="SABER/BUMP stddev NetCDF file")
    parser.add_argument("--nicas-dir", required=True, help="NICAS directory")
    parser.add_argument("--vbal-dir", required=True, help="VBAL directory")
    parser.add_argument("--strict", action="store_true", help="Treat missing variables as errors")
    args = parser.parse_args()

    variable_map = load_yaml(args.map)
    profile_name, profile = resolve_profile(variable_map, args.profile)

    analysis = profile.get("analysis_variables", {})
    state = profile.get("state_variables", {})
    validation = profile.get("validation", {})
    background_candidates = validation.get("background_candidates", {}) or {}
    saber = profile.get("saber_bump", {})
    control = saber.get("control_variables", {})

    analysis_variables = resolve_order(
        list(analysis.get("order", [])),
        dict(analysis.get("canonical_to_model", {})),
    )
    state_variables = resolve_order(
        list(state.get("order", [])),
        dict(state.get("canonical_to_model", {})),
        list(state.get("direct_model", [])),
    )
    control_variables = resolve_order(
        list(control.get("order", [])),
        dict(control.get("canonical_to_bump", {})),
    )
    bump_3d = list(saber.get("variables_3d", []))
    bump_2d = list(saber.get("variables_2d", []))
    vbal_entries = list(saber.get("vertical_balance", []))
    vbal_variables = sorted(
        {
            item[key]
            for item in vbal_entries
            for key in ("balanced_variable", "unbalanced_variable")
            if key in item
        }
    )

    background = expand_path(args.background)
    stddev = expand_path(args.stddev)
    nicas_dir = expand_path(args.nicas_dir)
    vbal_dir = expand_path(args.vbal_dir)

    print(f"[INFO] Variable profile: {profile_name}")
    print(f"[INFO] Background: {background}")
    print(f"[INFO] StdDev: {stddev}")
    print(f"[INFO] NICAS dir: {nicas_dir}")
    print(f"[INFO] VBAL dir: {vbal_dir}")

    status = STATUS_OK

    try:
        background_vars = ncdump_variables(background)
        stddev_vars = ncdump_variables(stddev)
    except Exception as exc:
        print(f"[ERROR] Failed to inspect required NetCDF input: {exc}")
        return STATUS_ERROR

    nicas_file = first_existing_file(nicas_dir, "*.nc")
    vbal_file = first_existing_file(vbal_dir, "*.nc")

    if nicas_file:
        print(f"[INFO] NICAS sample file: {nicas_file}")
        try:
            nicas_vars = ncdump_variables(nicas_file)
        except Exception as exc:
            print(f"[WARN] Failed to inspect NICAS sample file: {exc}")
            nicas_vars = set()
            status = max(status, STATUS_WARN)
    else:
        print(f"[WARN] No NICAS NetCDF sample file found in {nicas_dir}")
        nicas_vars = set()
        status = max(status, STATUS_WARN)

    if vbal_file:
        print(f"[INFO] VBAL sample file: {vbal_file}")
        try:
            vbal_vars = ncdump_variables(vbal_file)
        except Exception as exc:
            print(f"[WARN] Failed to inspect VBAL sample file: {exc}")
            vbal_vars = set()
            status = max(status, STATUS_WARN)
    else:
        print(f"[WARN] No VBAL NetCDF sample file found in {vbal_dir}")
        vbal_vars = set()
        status = max(status, STATUS_WARN)

    status = max(
        status,
        report_candidate_check(
            "analysis variables in background",
            analysis_variables,
            background_vars,
            background_candidates,
            args.strict,
        ),
    )

    status = max(
        status,
        report_candidate_check(
            "state variables in background",
            state_variables,
            background_vars,
            background_candidates,
            args.strict,
        ),
    )

    status = max(
        status,
        report_check(
            "BUMP control variables in stddev",
            control_variables,
            stddev_vars,
            args.strict,
        ),
    )

    status = max(
        status,
        report_check(
            "BUMP 3D variables in stddev",
            bump_3d,
            stddev_vars,
            args.strict,
        ),
    )

    status = max(
        status,
        report_check(
            "BUMP 2D variables in stddev",
            bump_2d,
            stddev_vars,
            args.strict,
        ),
    )

    # NICAS and VBAL local files are implementation-specific. When these files do not expose
    # the same variable names directly, the stddev checks above remain the authoritative
    # lightweight validation for mapped BUMP variables.
    if nicas_vars:
        overlap = sorted(set(control_variables) & nicas_vars)
        print(f"[INFO] NICAS sample/control-name overlap: {overlap if overlap else 'none'}")
    if vbal_vars:
        overlap = sorted(set(vbal_variables) & vbal_vars)
        print(f"[INFO] VBAL sample/vertical-balance-name overlap: {overlap if overlap else 'none'}")

    if status == STATUS_OK:
        print("[INFO] Variable map validation completed")
        return 0
    if args.strict:
        print("[ERROR] Variable map validation failed")
        return STATUS_ERROR

    print("[WARN] Variable map validation completed with warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
