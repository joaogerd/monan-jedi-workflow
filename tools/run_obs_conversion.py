#!/usr/bin/env python3
"""Run generic observation conversion commands from a YAML manifest.

This tool is intentionally converter-agnostic. It reads an experiment manifest,
expands environment variables, resolves command templates, and optionally runs
one conversion command per observation entry.

The manifest may describe PREPBUFR-to-IODA conversion, BUFR-to-IODA conversion,
or any other observation conversion supported by the local JEDI/iodaconv stack.
The workflow should not hard-code converter-specific command lines.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("[ERROR] PyYAML is required to run this tool") from exc


STATUS_OK = 0
STATUS_WARN = 1
STATUS_ERROR = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError(f"manifest must contain a mapping: {path}")
    return data


def expand_text(value: Any) -> str:
    return os.path.expandvars(str(value))


def expand_path(value: Any) -> Path:
    return Path(expand_text(value)).expanduser()


def resolve_converter(manifest: dict[str, Any]) -> str:
    converter = manifest.get("converter", {}) or {}
    if not isinstance(converter, dict):
        raise ValueError("converter section must be a mapping")

    env_name = converter.get("executable_env")
    if env_name:
        env_value = os.environ.get(str(env_name), "").strip()
        if env_value:
            return env_value

    executable = converter.get("executable") or converter.get("default_executable")
    if not executable:
        raise ValueError("converter executable not configured")
    return expand_text(executable)


def normalize_command(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return shlex.split(value)
    raise ValueError(f"invalid command value: {value!r}")


def render_token(token: str, context: dict[str, str]) -> str:
    rendered = token
    for key, value in context.items():
        rendered = rendered.replace("{" + key + "}", value)
    return os.path.expandvars(rendered)


def build_command(entry: dict[str, Any], converter_exe: str) -> list[str]:
    source_file = expand_text(entry.get("source_file") or entry.get("prepbufr_file") or "")
    target_file = expand_text(entry.get("target_file") or entry.get("output_file") or "")
    name = str(entry.get("name", "unnamed"))
    group = str(entry.get("group", name))

    context = {
        "name": name,
        "group": group,
        "source_file": source_file,
        "prepbufr_file": source_file,
        "target_file": target_file,
        "output_file": target_file,
    }

    if "command" in entry:
        template = normalize_command(entry.get("command"))
    else:
        template = [converter_exe]
        template.extend(normalize_command(entry.get("converter_args")))
        if "{source_file}" not in " ".join(template):
            template.extend(["--input", "{source_file}"])
        if "{target_file}" not in " ".join(template):
            template.extend(["--output", "{target_file}"])

    return [render_token(token, context) for token in template]


def manifest_observations(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    observations = manifest.get("observations", [])
    if not isinstance(observations, list):
        raise ValueError("observations section must be a list")
    return [item for item in observations if isinstance(item, dict)]


def write_trace_header(trace: Path, manifest_path: Path, execute: bool, strict: bool) -> None:
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(
        "obs_conversion:\n"
        f"  generated_by: tools/run_obs_conversion.py\n"
        f"  started_at_utc: {utc_now()}\n"
        f"  manifest: {manifest_path}\n"
        f"  execute: {str(execute).lower()}\n"
        f"  strict: {str(strict).lower()}\n"
        "  observations:\n",
        encoding="utf-8",
    )


def append_trace_observation(
    trace: Path,
    *,
    name: str,
    source: Path,
    target: Path,
    command: list[str],
    status: str,
    returncode: int | None = None,
) -> None:
    with trace.open("a", encoding="utf-8") as stream:
        stream.write(f"    - name: {name}\n")
        stream.write(f"      source: {source}\n")
        stream.write(f"      target: {target}\n")
        stream.write(f"      source_exists: {str(source.exists()).lower()}\n")
        stream.write(f"      target_exists: {str(target.exists()).lower()}\n")
        stream.write(f"      status: {status}\n")
        if returncode is not None:
            stream.write(f"      returncode: {returncode}\n")
        stream.write(f"      command: {shlex.join(command)}\n")


def append_trace_result(trace: Path, status: str, exit_code: int) -> None:
    with trace.open("a", encoding="utf-8") as stream:
        stream.write("  result:\n")
        stream.write(f"    status: {status}\n")
        stream.write(f"    exit_code: {exit_code}\n")
        stream.write(f"    finished_at_utc: {utc_now()}\n")


def run_command(command: list[str], log_file: Path | None) -> int:
    if log_file is None:
        completed = subprocess.run(command, check=False)
        return int(completed.returncode)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8") as stream:
        stream.write(f"# started_at_utc: {utc_now()}\n")
        stream.write(f"# command: {shlex.join(command)}\n\n")
        stream.flush()
        completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
        stream.write(f"\n# finished_at_utc: {utc_now()}\n")
        stream.write(f"# returncode: {completed.returncode}\n")
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Observation conversion manifest YAML")
    parser.add_argument("--trace", type=Path, default=Path("build/rendered/provenance/obs_conversion.trace"))
    parser.add_argument("--execute", action="store_true", help="Run converter commands")
    parser.add_argument("--strict", action="store_true", help="Fail on missing inputs or failed outputs")
    parser.add_argument("--only", action="append", default=[], help="Run only selected observation names")
    args = parser.parse_args()

    try:
        manifest = load_yaml(args.manifest)
        converter_exe = resolve_converter(manifest)
        observations = manifest_observations(manifest)
    except Exception as exc:
        print(f"[ERROR] Failed to load observation conversion manifest: {exc}")
        return STATUS_ERROR

    selected = set(args.only)
    paths = manifest.get("paths", {}) or {}
    log_dir = expand_path(paths.get("log_dir", "build/logs/obs_conversion"))

    print("[INFO] Observation conversion manifest")
    print(f"[INFO]   manifest : {args.manifest}")
    print(f"[INFO]   converter: {converter_exe}")
    print(f"[INFO]   execute  : {args.execute}")
    print(f"[INFO]   strict   : {args.strict}")
    print(f"[INFO]   trace    : {args.trace}")

    write_trace_header(args.trace, args.manifest, args.execute, args.strict)

    status = STATUS_OK
    enabled_count = 0

    for entry in observations:
        name = str(entry.get("name", "unnamed"))
        if selected and name not in selected:
            continue
        if not bool(entry.get("enabled", True)):
            continue

        enabled_count += 1
        source = expand_path(entry.get("source_file") or entry.get("prepbufr_file") or "")
        target = expand_path(entry.get("target_file") or entry.get("output_file") or "")
        command = build_command(entry, converter_exe)
        log_file = log_dir / f"{name}.log"

        print(f"[INFO] observation={name}")
        print(f"[INFO]   source: {source}")
        print(f"[INFO]   target: {target}")
        print(f"[INFO]   command: {shlex.join(command)}")

        if not source.exists():
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] Missing source observation file for {name}: {source}")
            status = max(status, STATUS_ERROR if args.strict else STATUS_WARN)
            append_trace_observation(
                args.trace,
                name=name,
                source=source,
                target=target,
                command=command,
                status="missing_source",
            )
            continue

        if not args.execute:
            append_trace_observation(
                args.trace,
                name=name,
                source=source,
                target=target,
                command=command,
                status="planned",
            )
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        rc = run_command(command, log_file)
        if rc != 0:
            print(f"[ERROR] Conversion failed for {name}; returncode={rc}; log={log_file}")
            status = STATUS_ERROR
            append_trace_observation(
                args.trace,
                name=name,
                source=source,
                target=target,
                command=command,
                status="failed",
                returncode=rc,
            )
            continue

        if not target.exists():
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] Conversion finished but target is missing for {name}: {target}")
            status = max(status, STATUS_ERROR if args.strict else STATUS_WARN)
            append_trace_observation(
                args.trace,
                name=name,
                source=source,
                target=target,
                command=command,
                status="target_missing",
                returncode=rc,
            )
            continue

        print(f"[INFO] Conversion completed for {name}: {target}")
        append_trace_observation(
            args.trace,
            name=name,
            source=source,
            target=target,
            command=command,
            status="completed",
            returncode=rc,
        )

    if enabled_count == 0:
        print("[WARN] No enabled observation conversion entries were selected")
        status = max(status, STATUS_WARN)

    if status == STATUS_OK:
        append_trace_result(args.trace, "completed", 0)
        print("[INFO] Observation conversion planning/execution completed")
        return 0

    if status == STATUS_ERROR:
        append_trace_result(args.trace, "failed", STATUS_ERROR)
        return STATUS_ERROR

    append_trace_result(args.trace, "completed_with_warnings", 0)
    if args.strict:
        return STATUS_ERROR
    return 0


if __name__ == "__main__":
    sys.exit(main())
