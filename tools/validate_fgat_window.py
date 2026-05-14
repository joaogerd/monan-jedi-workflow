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
ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_cycle(value: str) -> tuple[str, datetime]:
    text = str(value).strip()
    if CYCLE_RE.match(text):
        return text, datetime.strptime(text, "%Y%m%d%H")
    if ISO_UTC_RE.match(text):
        dt = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%Y%m%d%H"), dt
    raise ValueError(f"cycle must be YYYYMMDDHH or ISO UTC, got {value!r}")


def parse_duration_hours(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    match = re.match(r"^(\d+(?:\.\d+)?)(h|hr|hour|hours)?$", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.match(r"^PT(-?\d+(?:\.\d+)?)H$", text, re.IGNORECASE)
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


def find_time_windows(node: Any) -> list[Any]:
    windows: list[Any] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key) in {"time window", "time_window", "window"}:
                windows.append(value)
            windows.extend(find_time_windows(value))
    elif isinstance(node, list):
        for value in node:
            windows.extend(find_time_windows(value))
    return windows


def extract_date_tokens(text: str) -> list[str]:
    return DATE_TOKEN_RE.findall(text)


def load_document(path: Path) -> dict[str, Any]:
    data = read_yaml(path)
    if not isinstance(data, dict):
        raise ValueError("experiment file must be a YAML mapping")
    return data


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
    doc = load_document(args.experiment)
    exp = doc.get("experiment", {})
    assim = doc.get("assimilation", {})
    if not isinstance(exp, dict):
        exp = {}
    if not isinstance(assim, dict):
        assim = {}

    cycle_source = exp.get("cycle", exp.get("start_cycle", exp.get("analysis_time", "")))
    if not cycle_source:
        print("[ERROR] experiment cycle is missing; expected experiment.cycle, start_cycle or analysis_time")
        return 2

    try:
        cycle, cycle_dt = parse_cycle(str(cycle_source))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    print(f"[INFO] Experiment cycle: {cycle} ({cycle_dt.isoformat()}Z)")

    window = exp.get("window", {})
    if not isinstance(window, dict):
        window = {}

    window_begin = str(
        window.get(
            "begin",
            window.get("start", assim.get("window_begin", assim.get("window_start", ""))),
        )
    )
    window_length = window.get(
        "length",
        window.get("duration_hours", assim.get("window_length", assim.get("window_duration_hours"))),
    )
    begin_offset_hours = parse_duration_hours(window_begin)
    length_hours = parse_duration_hours(window_length)

    if window_begin:
        print(f"[INFO] Assimilation window begin declaration: {window_begin}")
        if begin_offset_hours is not None:
            print(f"[INFO] Inferred window begin: {(cycle_dt + timedelta(hours=begin_offset_hours)).isoformat()}Z")
    else:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] assimilation window begin/start is not declared")
        ok = ok and not args.strict

    if length_hours is None:
        level = "ERROR" if args.strict else "WARN"
        print(f"[{level}] assimilation window length/duration_hours is not declared or not parseable")
        ok = ok and not args.strict
    else:
        print(f"[INFO] Assimilation window length: {length_hours} hours")
        if begin_offset_hours is not None:
            end_dt = cycle_dt + timedelta(hours=begin_offset_hours + length_hours)
        else:
            end_dt = cycle_dt + timedelta(hours=length_hours)
        print(f"[INFO] Inferred window end: {end_dt.isoformat()}Z")

    render_context = read_yaml(args.render_context)
    context_cycles = find_values_by_key(render_context, {"cycle", "cycle_date", "analysis_time", "start_cycle"})
    print(f"[INFO] Render context temporal values: {context_cycles}")
    if context_cycles and not any(cycle in str(value) or str(cycle_source) in str(value) for value in context_cycles):
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
            {"window begin", "window length", "window_begin", "window_length", "analysis date", "analysis_date", "cycle"},
        )
        time_windows = find_time_windows(jedi)
        print(f"[INFO] Rendered JEDI temporal values: {temporal_values}")
        print(f"[INFO] Rendered JEDI time windows: {time_windows}")
        if not temporal_values and not time_windows:
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
