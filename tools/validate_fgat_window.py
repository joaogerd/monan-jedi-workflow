#!/usr/bin/env python3
"""Validate structural consistency of a MONAN-JEDI 3DVar-FGAT window.

This validator compares temporal metadata declared in the experiment
configuration, render context, IODA inventory, and rendered JEDI YAML. It is a
structural provenance check: it verifies whether the declared cycle and window
information are visible and internally consistent across workflow files.

The script does not inspect observation timestamps inside IODA/HDF5 files. That
scientific validation belongs to a dedicated observation-content validator. Here,
the goal is to catch common workflow mistakes such as mismatched cycle tokens,
missing window declarations, or rendered YAML files that no longer contain an
obvious assimilation-window section.

Examples
--------
Validate the default 3DVar-FGAT metadata in permissive mode::

    $ python tools/validate_fgat_window.py

Validate a rendered experiment and fail on missing or ambiguous metadata::

    $ python tools/validate_fgat_window.py \
        --experiment configs/experiments/3dvar_fgat/experiment.yaml \
        --render-context configs/experiments/3dvar_fgat/render_context.yaml \
        --jedi-yaml build/rendered/3dvar_fgat.yaml \
        --ioda-inventory configs/experiments/3dvar_fgat/ioda_inventory.yaml \
        --strict
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

# Supported experiment cycle format: YYYYMMDDHH, for example 2018041500.
CYCLE_RE = re.compile(r"^\d{10}$")

# Date tokens embedded in filenames are commonly used in staged JEDI inputs.
DATE_TOKEN_RE = re.compile(r"(\d{10})")

# ISO UTC format commonly used by JEDI YAML files.
ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def read_yaml(path: Path) -> Any:
    """Read a YAML document from disk.

    Parameters
    ----------
    path : pathlib.Path
        Path to the YAML file that will be read as UTF-8 text.

    Returns
    -------
    Any
        Python object produced by ``yaml.safe_load``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist or is not a regular file.
    yaml.YAMLError
        If the file content is not valid YAML.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read due to permissions or another filesystem
        error.

    Notes
    -----
    The function intentionally performs only generic YAML loading. Schema checks
    are implemented by higher-level helpers so each input file can have its own
    validation rules.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.
    load_document : Read and validate the experiment document root.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("cycle.yaml")
    >>> _ = path.write_text("experiment:\n  cycle: 2018041500\n", encoding="utf-8")
    >>> read_yaml(path)["experiment"]["cycle"]
    2018041500
    >>> path.unlink()
    """
    if not path.is_file():
        raise FileNotFoundError(str(path))

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_cycle(value: str) -> tuple[str, datetime]:
    """Parse a cycle declaration into compact and datetime representations.

    Parameters
    ----------
    value : str
        Cycle value in either ``YYYYMMDDHH`` format or ISO UTC format
        ``YYYY-MM-DDTHH:MM:SSZ``.

    Returns
    -------
    tuple of str and datetime.datetime
        Compact cycle string in ``YYYYMMDDHH`` format and the corresponding
        naive UTC ``datetime`` object.

    Raises
    ------
    ValueError
        If ``value`` is not in one of the supported cycle formats.

    Notes
    -----
    The returned ``datetime`` is naive but represents UTC. This mirrors the way
    many JEDI YAML files encode UTC timestamps with a trailing ``Z`` while Python
    workflow scripts handle them as simple datetimes.

    See Also
    --------
    datetime.datetime.strptime : Parse datetime strings.
    parse_duration_hours : Parse assimilation-window offsets and lengths.

    Examples
    --------
    >>> parse_cycle("2018041500")[0]
    '2018041500'
    >>> parse_cycle("2018-04-15T00:00:00Z")[0]
    '2018041500'
    """
    text = str(value).strip()
    if CYCLE_RE.match(text):
        return text, datetime.strptime(text, "%Y%m%d%H")

    if ISO_UTC_RE.match(text):
        dt = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%Y%m%d%H"), dt

    raise ValueError(f"cycle must be YYYYMMDDHH or ISO UTC, got {value!r}")


def parse_duration_hours(value: Any) -> float | None:
    """Parse a duration or offset value expressed in hours.

    Parameters
    ----------
    value : Any
        Duration value. Supported inputs include numeric values, strings such as
        ``"6"``, ``"6h"``, ``"6 hours"``, and ISO-8601-like values such as
        ``"PT6H"``.

    Returns
    -------
    float or None
        Duration in hours when parsing succeeds. Returns ``None`` when the value
        is missing or not recognized.

    Raises
    ------
    None
        This function is intentionally non-raising for unrecognized values so the
        caller can decide whether the problem should be a warning or an error.

    Notes
    -----
    Negative ISO-hour values are accepted for window-begin offsets, because FGAT
    windows are often declared relative to the analysis time, for example
    ``PT-3H`` in some configuration styles.

    See Also
    --------
    parse_cycle : Parse the reference analysis cycle.
    re.match : Match supported textual duration patterns.

    Examples
    --------
    >>> parse_duration_hours("6h")
    6.0
    >>> parse_duration_hours("PT-3H")
    -3.0
    >>> parse_duration_hours("not-a-duration") is None
    True
    """
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
    """Recursively collect values whose keys match a target set.

    Parameters
    ----------
    node : Any
        YAML-derived object to inspect. Dictionaries and lists are traversed
        recursively; scalar values are ignored.
    key_names : set of str
        Exact key names to collect.

    Returns
    -------
    list of Any
        Values associated with matching keys, preserving discovery order from the
        traversal.

    Raises
    ------
    None
        The function does not raise for unsupported node types; scalar values
        simply produce an empty list.

    Notes
    -----
    This helper avoids assuming a single JEDI schema. Rendered YAML files may use
    slightly different keys for analysis dates and window lengths depending on
    the application block being rendered.

    See Also
    --------
    find_time_windows : Specialized recursive search for time-window mappings.

    Examples
    --------
    >>> find_values_by_key({"a": {"cycle": "2018041500"}}, {"cycle"})
    ['2018041500']
    """
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
    """Recursively collect time-window declarations from a YAML object.

    Parameters
    ----------
    node : Any
        YAML-derived object to inspect.

    Returns
    -------
    list of Any
        Values associated with keys commonly used for time-window declarations:
        ``time window``, ``time_window``, and ``window``.

    Raises
    ------
    None
        Unsupported node types are ignored.

    Notes
    -----
    Both space-separated and underscore-separated key styles are supported
    because JEDI application YAML and workflow metadata may use different naming
    conventions.

    See Also
    --------
    find_values_by_key : Generic recursive key-value search.

    Examples
    --------
    >>> find_time_windows({"outer": {"time window": {"begin": "2018"}}})
    [{'begin': '2018'}]
    """
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
    """Extract compact cycle-like date tokens from text.

    Parameters
    ----------
    text : str
        Text to inspect, typically a staged IODA file path.

    Returns
    -------
    list of str
        All ten-digit tokens matching ``YYYYMMDDHH``-like patterns.

    Raises
    ------
    TypeError
        If ``text`` is not a string.

    Notes
    -----
    The function only extracts lexical tokens. It does not verify whether the
    token is a valid calendar date.

    See Also
    --------
    DATE_TOKEN_RE : Regular expression used for token extraction.

    Examples
    --------
    >>> extract_date_tokens("ioda/aircraft_2018041500.nc4")
    ['2018041500']
    """
    return DATE_TOKEN_RE.findall(text)


def load_document(path: Path) -> dict[str, Any]:
    """Load an experiment YAML file and require a mapping root.

    Parameters
    ----------
    path : pathlib.Path
        Path to the experiment YAML file.

    Returns
    -------
    dict of str to Any
        Experiment document as a dictionary.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the YAML root is not a mapping.
    yaml.YAMLError
        If the file is not valid YAML.

    Notes
    -----
    The experiment file is the authoritative source for the cycle used by this
    validator. Requiring a mapping at this level prevents confusing downstream
    errors when the wrong file is passed.

    See Also
    --------
    read_yaml : Generic YAML loader used by this function.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("experiment.yaml")
    >>> _ = path.write_text("experiment:\n  cycle: 2018041500\n", encoding="utf-8")
    >>> sorted(load_document(path).keys())
    ['experiment']
    >>> path.unlink()
    """
    data = read_yaml(path)
    if not isinstance(data, dict):
        raise ValueError("experiment file must be a YAML mapping")

    return data


def ioda_paths(path: Path) -> list[str]:
    """Read IODA file paths from an inventory YAML file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the IODA inventory YAML file.

    Returns
    -------
    list of str
        File paths declared under ``ioda_inventory.observations`` or
        ``ioda_inventory.files``. Each entry may use ``path``, ``target``, or
        ``file`` as the path key.

    Raises
    ------
    FileNotFoundError
        If the inventory file does not exist.
    ValueError
        If the inventory does not contain the expected mapping/list structure.
    yaml.YAMLError
        If the inventory is not valid YAML.

    Notes
    -----
    The function accepts multiple key names to support gradual evolution of the
    MONAN-JEDI inventory schema without forcing old examples to be rewritten.

    See Also
    --------
    read_yaml : Read the inventory YAML document.
    extract_date_tokens : Extract cycle-like tokens from returned paths.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("ioda_inventory.yaml")
    >>> _ = path.write_text("ioda_inventory:\n  files:\n    - path: obs_2018041500.nc4\n", encoding="utf-8")
    >>> ioda_paths(path)
    ['obs_2018041500.nc4']
    >>> path.unlink()
    """
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
    """Run the FGAT window structural validator.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when validation passes under the selected
        policy and ``2`` when a required structural check fails.

    Raises
    ------
    FileNotFoundError
        If a required YAML file path does not exist.
    yaml.YAMLError
        If one of the YAML files cannot be parsed.
    OSError
        If a file cannot be read.

    Notes
    -----
    Strict mode turns missing or ambiguous metadata into failures. Without strict
    mode, the same findings are generally reported as warnings so the tool can be
    used during early documentation or bootstrap stages.

    See Also
    --------
    parse_cycle : Parse the experiment cycle.
    parse_duration_hours : Parse window offsets and lengths.
    ioda_paths : Read observation paths from an IODA inventory.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
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

    # The cycle may be named differently in older workflow drafts. Keep the
    # fallback sequence explicit so provenance checks remain backward-compatible.
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
