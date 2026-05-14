#!/usr/bin/env python3
"""Validate structural consistency of the 3DVar-FGAT assimilation window.

This validator checks dates and window metadata across experiment configuration,
render context, IODA inventory and rendered JEDI YAML. It does not validate the
actual temporal distribution of observations inside IODA files.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


CYCLE_RE = re.compile(r"^\d{10}$")
DATE_TOKEN_RE = re.compile(r"(\d{10})")


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_cycle(cycle: str) -> datetime:
    if not CYCLE_RE.match(cycle):
        raise ValueError(f"cycle must be YYYYMMDDHH, got {cycle!r}")
    return datetime.strptime(cycle, "%Y%m%d%H")


def parse_duration_hours(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    match = re.match(r"^(\d+(?:\.\d+)?)(h|hr|hour|hours)?$", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.match(r"^PT(\d+(?:\.\d+)?)H$", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def find_values_by_key(node: Any, key_names: set[str]) -> list[Any]:
    found: list[Any] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key) in key_names:
                found.append(value)
            found.extend(find_values_by_key(value, key_names))
    elif isinstance(node, list):
        for value in node:
            found.extend(find_values_by_key(value, key_names))
    return found


def extract_date_tokens(text: str) -> list[str]:
    return DATE_TOKEN_RE.findall(text)


def experiment_root(path: Path) -> dict[str, Any]:
    data = read_yaml(path)
    root = data.get("experiment") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        raise ValueError("experiment file must contain experiment mapping")
    return root


def ioda_paths(path: Path) -> list[str]:
    data = read_yaml(path)
    root = data.get("ioda_inventory") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        raise ValueError("IODA inventory must contain ioda_inventory mapping")
    entries = root.get("observations", root.get("files", []))
    if not isinstance(entries, list):
        raise ValueError("IODA inventory observations/files must be a list")
    paths: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        value = item.get("path", item.get("target", item.get("file", "")))
        if value:
            paths.append(str(value))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate structural 3DVar-FGAT window consistency.")
    parser.add_argument(
        "--experiment",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/experiment.yaml"),
    )
    parser.add_argument(
        "--render-context",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/render_context.example.yaml"),
    )
    parser.add_argument(
        "--jedi-yaml",
        type=Path,
        default=Path("build/rendered/3dvar_fgat.yaml"),
    )
    parser.add_argument(
        "--ioda-inventory",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/ioda_inventory.example.yaml"),
    )
    parser.add_argument("--strict", action="store_true", help="Fail on missing/ambiguous temporal metadata.")
    args = parser.parse_args()

    ok = True
    exp = experiment_root(args.experiment)
    cycle = str(exp.get("cycle", ""))
    if not cycle:
        print("[ERROR] experiment.cycle is missing")
        return 2

    try:
        cycle_dt = parse_cycle(cycle)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    print(f"[INFO] Experiment cycle: {cycle} ({cycle_dt.isoformat()}Z)")

    window = exp.get("window", {})
    if not isinstance(window, dict):
        window = {}

    window_begin = str(window.get("begin", window.get("start", "")))
    window_length = window.get("length", window.get("duration_hours"))
    length_hours = parse_duration_hours(window_length)

    if window_begin:
        print(f"[INFO] Experiment window begin: {window_begin}")
    else:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] experiment.window.begin/start is not declared")
        ok = ok and not args.strict

    if length_hours is None:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] experiment window length/duration_hours is not declared or not parseable")
        ok = ok and not args.strict
    else:
        print(f"[INFO] Experiment window length: {length_hours} hours")
        print(f"[INFO] Inferred window end: {(cycle_dt + timedelta(hours=length_hours)).isoformat()}Z")

    render_context = read_yaml(args.render_context)
    context_cycles = find_values_by_key(render_context, {"cycle", "cycle_date", "analysis_time"})
    print(f"[INFO] Render context temporal values: {context_cycles}")
    if context_cycles and not any(cycle in str(value) for value in context_cycles):
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] render context does not visibly contain experiment cycle {cycle}")
        ok = ok and not args.strict

    for path_text in ioda_paths(args.ioda_inventory):
        tokens = extract_date_tokens(path_text)
        if tokens and cycle not in tokens:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] IODA path date token does not match cycle: {path_text} tokens={tokens}")
            ok = ok and not args.strict
        else:
            print(f"[INFO] IODA path temporal token check passed: {path_text}")

    if args.jedi_yaml.is_file():
        jedi = read_yaml(args.jedi_yaml)
        temporal_values = find_values_by_key(
            jedi,
            {"window begin", "window length", "window_begin", "window_length", "analysis date", "analysis_date"},
        )
        print(f"[INFO] Rendered JEDI temporal values: {temporal_values}")
        if not temporal_values:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] no obvious temporal/window keys found in rendered JEDI YAML")
            ok = ok and not args.strict
    else:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] rendered JEDI YAML not found: {args.jedi_yaml}")
        ok = ok and not args.strict

    if not ok:
        return 2

    print("[INFO] FGAT window structural validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
