#!/usr/bin/env python3
"""Run generic observation conversion commands from a YAML manifest.

The driver is intentionally converter-agnostic. It supports two manifest styles:

1. stage-based conversion, used to mirror MPAS-Workflow PrepareObservations;
2. legacy one-command-per-observation conversion.

For native obs2ioda v3 conversion, prefer absolute input/output directories:

    obs2ioda-v3 -i /abs/input_dir -o /abs/output_dir prepbufr-file

The driver normalizes stage input_dir/output_dir/work_dir with real paths before
rendering the command. This avoids silent no-output runs caused by fragile
relative paths.
"""

from __future__ import annotations

import argparse
import os
import shutil
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


def real_existing_dir(value: Any) -> str:
    path = expand_path(value)
    return str(path.resolve(strict=True))


def real_output_dir(value: Any) -> str:
    path = expand_path(value)
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve(strict=False))


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


def render_command(tokens: list[str], context: dict[str, str]) -> list[str]:
    return [render_token(token, context) for token in tokens]


def resolve_executable(name: str, manifest: dict[str, Any]) -> str:
    executables = manifest.get("executables", {}) or {}
    item = executables.get(name, {}) if isinstance(executables, dict) else {}
    if not isinstance(item, dict):
        raise ValueError(f"executable entry must be a mapping: {name}")

    env_name = item.get("executable_env")
    if env_name:
        env_value = os.environ.get(str(env_name), "").strip()
        if env_value:
            return env_value

    default_executable = item.get("default_executable")
    build_dir_env = item.get("build_dir_env")
    if build_dir_env and default_executable:
        build_dir = os.environ.get(str(build_dir_env), "").strip()
        if build_dir:
            return str(Path(build_dir).expanduser() / str(default_executable))

    executable = item.get("executable") or default_executable
    if not executable:
        raise ValueError(f"executable not configured: {name}")
    return expand_text(executable)


def executable_context(manifest: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    executables = manifest.get("executables", {}) or {}
    if not isinstance(executables, dict):
        return result
    for name in executables:
        result[name] = resolve_executable(str(name), manifest)
    return result


def source_context(stage: dict[str, Any], manifest: dict[str, Any]) -> dict[str, str]:
    sources = manifest.get("sources", {}) or {}
    source_name = stage.get("source")
    source_file = ""
    source_file_name = ""
    input_dir = ""

    if source_name and isinstance(sources, dict):
        source = sources.get(str(source_name), {}) or {}
        if isinstance(source, dict):
            source_file = expand_text(source.get("file", ""))
            source_file_name = str(source.get("file_name", ""))
            input_dir = expand_text(source.get("input_dir", ""))

    source_file = expand_text(stage.get("source_file", source_file))
    source_file_name = str(stage.get("source_file_name", source_file_name))
    input_dir = expand_text(stage.get("input_dir", input_dir))

    if source_file and not source_file_name:
        source_file_name = Path(source_file).name
    if source_file and not input_dir:
        input_dir = str(Path(source_file).parent)

    return {
        "source_file": source_file,
        "prepbufr_file": source_file,
        "source_file_name": source_file_name,
        "bufr_file": source_file_name,
        "input_dir": input_dir,
    }


def base_context(manifest: dict[str, Any]) -> dict[str, str]:
    experiment = manifest.get("experiment", {}) or {}
    paths = manifest.get("paths", {}) or {}
    context = {
        "cycle": str(experiment.get("cycle", "")),
        "prepbufr_dir": expand_text(paths.get("prepbufr_dir", "")),
        "ioda_dir": expand_text(paths.get("ioda_dir", "")),
        "log_dir": expand_text(paths.get("log_dir", "build/logs/obs_conversion")),
    }
    context.update(executable_context(manifest))
    return context


def write_trace_header(trace: Path, manifest_path: Path, execute: bool, strict: bool) -> None:
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(
        "obs_conversion:\n"
        f"  generated_by: tools/run_obs_conversion.py\n"
        f"  started_at_utc: {utc_now()}\n"
        f"  manifest: {manifest_path}\n"
        f"  execute: {str(execute).lower()}\n"
        f"  strict: {str(strict).lower()}\n"
        "  stages:\n",
        encoding="utf-8",
    )


def append_trace_stage(trace: Path, data: dict[str, Any]) -> None:
    with trace.open("a", encoding="utf-8") as stream:
        stream.write(f"    - name: {data.get('name')}\n")
        stream.write(f"      kind: {data.get('kind')}\n")
        stream.write(f"      status: {data.get('status')}\n")
        if data.get("work_dir"):
            stream.write(f"      work_dir: {data.get('work_dir')}\n")
        if data.get("input_dir"):
            stream.write(f"      input_dir: {data.get('input_dir')}\n")
        if data.get("output_dir"):
            stream.write(f"      output_dir: {data.get('output_dir')}\n")
        if data.get("source"):
            stream.write(f"      source: {data.get('source')}\n")
            stream.write(f"      source_exists: {str(data.get('source_exists')).lower()}\n")
        if data.get("command"):
            stream.write(f"      command: {shlex.join(data.get('command'))}\n")
        if data.get("returncode") is not None:
            stream.write(f"      returncode: {data.get('returncode')}\n")
        if data.get("log_file"):
            stream.write(f"      log_file: {data.get('log_file')}\n")
        outputs = data.get("outputs") or []
        if outputs:
            stream.write("      outputs:\n")
            for output in outputs:
                stream.write(f"        - path: {output['path']}\n")
                stream.write(f"          exists: {str(output['exists']).lower()}\n")
        publishes = data.get("publishes") or []
        if publishes:
            stream.write("      publishes:\n")
            for item in publishes:
                stream.write(f"        - from: {item['from']}\n")
                stream.write(f"          to: {item['to']}\n")
                stream.write(f"          mode: {item['mode']}\n")
                stream.write(f"          status: {item['status']}\n")


def append_trace_final_products(trace: Path, manifest: dict[str, Any]) -> None:
    observations = manifest.get("observations", []) or []
    with trace.open("a", encoding="utf-8") as stream:
        stream.write("  final_observations:\n")
        for item in observations:
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            name = str(item.get("name", "unnamed"))
            source = expand_path(item.get("source_file") or item.get("prepbufr_file") or "")
            target = expand_path(item.get("target_file") or item.get("output_file") or "")
            stream.write(f"    - name: {name}\n")
            stream.write(f"      source: {source}\n")
            stream.write(f"      target: {target}\n")
            stream.write(f"      source_exists: {str(source.exists()).lower()}\n")
            stream.write(f"      target_exists: {str(target.exists()).lower()}\n")


def append_trace_result(trace: Path, status: str, exit_code: int) -> None:
    with trace.open("a", encoding="utf-8") as stream:
        stream.write("  result:\n")
        stream.write(f"    status: {status}\n")
        stream.write(f"    exit_code: {exit_code}\n")
        stream.write(f"    finished_at_utc: {utc_now()}\n")


def run_command(command: list[str], work_dir: Path, log_file: Path) -> int:
    work_dir.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8") as stream:
        stream.write(f"# started_at_utc: {utc_now()}\n")
        stream.write(f"# work_dir: {work_dir}\n")
        stream.write(f"# command: {shlex.join(command)}\n\n")
        stream.flush()
        completed = subprocess.run(command, cwd=work_dir, stdout=stream, stderr=subprocess.STDOUT, check=False)
        stream.write(f"\n# finished_at_utc: {utc_now()}\n")
        stream.write(f"# returncode: {completed.returncode}\n")
    return int(completed.returncode)


def expected_outputs(stage: dict[str, Any]) -> list[Path]:
    return [expand_path(item) for item in stage.get("expected_outputs", []) or []]


def output_status(paths: list[Path]) -> list[dict[str, Any]]:
    return [{"path": str(path), "exists": path.exists()} for path in paths]


def publish_outputs(stage: dict[str, Any], execute: bool) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in stage.get("publish", []) or []:
        if not isinstance(item, dict):
            continue
        src = expand_path(item.get("from", ""))
        dst = expand_path(item.get("to", ""))
        mode = str(item.get("mode", "copy"))
        status = "planned"
        if execute:
            if not src.exists():
                status = "missing_source"
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if mode == "move":
                    shutil.move(str(src), str(dst))
                elif mode == "symlink":
                    if dst.exists() or dst.is_symlink():
                        dst.unlink()
                    dst.symlink_to(src)
                else:
                    shutil.copy2(src, dst)
                status = "completed"
        results.append({"from": str(src), "to": str(dst), "mode": mode, "status": status})
    return results


def temp_output_for(path: Path, suffix: str) -> Path:
    return path.with_name(f"{path.stem}_{suffix}{path.suffix}")


def run_upgrade_stage(stage: dict[str, Any], manifest: dict[str, Any], context: dict[str, str], execute: bool, strict: bool, trace: Path) -> int:
    name = str(stage.get("name", "unnamed"))
    kind = str(stage.get("kind", "upgrade"))
    executable_key = str(stage.get("executable", ""))
    exe = context.get(executable_key) or resolve_executable(executable_key, manifest)
    config_file = expand_text(stage.get("config_file", ""))
    inputs = [expand_path(item) for item in stage.get("inputs", []) or []]
    status = STATUS_OK

    for input_file in inputs:
        if kind == "upgrade_v1_to_v2":
            tmp_file = temp_output_for(input_file, "v2_tmp")
            command = [exe, str(input_file), str(tmp_file)]
        elif kind == "upgrade_v2_to_v3":
            tmp_file = temp_output_for(input_file, "v3_tmp")
            command = [exe, str(input_file), str(tmp_file), config_file]
        else:
            print(f"[WARN] Unsupported upgrade kind for stage {name}: {kind}")
            status = max(status, STATUS_WARN)
            continue

        log_dir = expand_path((manifest.get("paths", {}) or {}).get("log_dir", "build/logs/obs_conversion"))
        log_file = log_dir / f"{name}_{input_file.stem}.log"
        work_dir = input_file.parent

        print(f"[INFO] stage={name} input={input_file}")
        print(f"[INFO]   command: {shlex.join(command)}")

        if not input_file.exists():
            level = "ERROR" if strict else "WARN"
            print(f"[{level}] Missing upgrade input: {input_file}")
            status = max(status, STATUS_ERROR if strict else STATUS_WARN)
            append_trace_stage(trace, {"name": f"{name}:{input_file.name}", "kind": kind, "status": "missing_input", "command": command, "outputs": output_status([input_file])})
            continue

        if not execute:
            append_trace_stage(trace, {"name": f"{name}:{input_file.name}", "kind": kind, "status": "planned", "command": command, "outputs": output_status([input_file])})
            continue

        rc = run_command(command, work_dir, log_file)
        if rc != 0 or not tmp_file.exists():
            print(f"[ERROR] Upgrade failed for {input_file}; returncode={rc}; log={log_file}")
            status = STATUS_ERROR
            append_trace_stage(trace, {"name": f"{name}:{input_file.name}", "kind": kind, "status": "failed", "command": command, "returncode": rc, "log_file": str(log_file), "outputs": output_status([tmp_file])})
            continue

        shutil.move(str(tmp_file), str(input_file))
        append_trace_stage(trace, {"name": f"{name}:{input_file.name}", "kind": kind, "status": "completed", "command": command, "returncode": rc, "log_file": str(log_file), "outputs": output_status([input_file])})

    return status


def run_command_stage(stage: dict[str, Any], manifest: dict[str, Any], context: dict[str, str], execute: bool, strict: bool, trace: Path) -> int:
    name = str(stage.get("name", "unnamed"))
    kind = str(stage.get("kind", "command"))
    stage_context = dict(context)
    stage_context.update(source_context(stage, manifest))

    try:
        input_dir = real_existing_dir(stage_context.get("input_dir") or stage.get("input_dir") or Path(stage_context.get("source_file", ".")).parent)
    except FileNotFoundError:
        input_dir = expand_text(stage_context.get("input_dir") or stage.get("input_dir") or Path(stage_context.get("source_file", ".")).parent)

    output_dir = real_output_dir(stage.get("output_dir", context.get("ioda_dir", ".")))
    work_dir = Path(real_output_dir(stage.get("work_dir", output_dir)))

    stage_context["input_dir"] = input_dir
    stage_context["output_dir"] = output_dir
    stage_context["work_dir"] = str(work_dir)

    source = Path(input_dir) / stage_context.get("source_file_name", "")
    if not source.name:
        source = expand_path(stage_context.get("source_file", ""))
    stage_context["source_file"] = str(source)
    stage_context["prepbufr_file"] = str(source)

    command = render_command(normalize_command(stage.get("command")), stage_context)
    outputs = expected_outputs(stage)
    log_dir = expand_path((manifest.get("paths", {}) or {}).get("log_dir", "build/logs/obs_conversion"))
    log_file = log_dir / f"{name}.log"

    print(f"[INFO] stage={name}")
    print(f"[INFO]   work_dir : {work_dir}")
    print(f"[INFO]   input_dir: {input_dir}")
    print(f"[INFO]   output_dir: {output_dir}")
    print(f"[INFO]   source   : {source}")
    print(f"[INFO]   command  : {shlex.join(command)}")

    if not source.exists():
        level = "ERROR" if strict else "WARN"
        print(f"[{level}] Missing source file for stage {name}: {source}")
        append_trace_stage(trace, {"name": name, "kind": kind, "status": "missing_source", "work_dir": str(work_dir), "input_dir": input_dir, "output_dir": output_dir, "source": str(source), "source_exists": False, "command": command, "outputs": output_status(outputs)})
        return STATUS_ERROR if strict else STATUS_WARN

    if not execute:
        publishes = publish_outputs(stage, execute=False)
        append_trace_stage(trace, {"name": name, "kind": kind, "status": "planned", "work_dir": str(work_dir), "input_dir": input_dir, "output_dir": output_dir, "source": str(source), "source_exists": True, "command": command, "outputs": output_status(outputs), "publishes": publishes})
        return STATUS_OK

    rc = run_command(command, work_dir, log_file)
    publishes = publish_outputs(stage, execute=True)
    missing = [path for path in outputs if not path.exists()]
    if rc != 0 or missing:
        if rc != 0:
            print(f"[ERROR] Stage failed: {name}; returncode={rc}; log={log_file}")
        if missing:
            print(f"[ERROR] Stage outputs missing: {', '.join(str(path) for path in missing)}")
        append_trace_stage(trace, {"name": name, "kind": kind, "status": "failed", "work_dir": str(work_dir), "input_dir": input_dir, "output_dir": output_dir, "source": str(source), "source_exists": True, "command": command, "returncode": rc, "log_file": str(log_file), "outputs": output_status(outputs), "publishes": publishes})
        return STATUS_ERROR

    append_trace_stage(trace, {"name": name, "kind": kind, "status": "completed", "work_dir": str(work_dir), "input_dir": input_dir, "output_dir": output_dir, "source": str(source), "source_exists": True, "command": command, "returncode": rc, "log_file": str(log_file), "outputs": output_status(outputs), "publishes": publishes})
    return STATUS_OK


def run_stages(manifest: dict[str, Any], args: argparse.Namespace) -> int:
    stages = manifest.get("stages", []) or []
    if not isinstance(stages, list):
        raise ValueError("stages section must be a list")

    selected = set(args.only)
    context = base_context(manifest)
    status = STATUS_OK
    enabled_count = 0

    for stage in stages:
        if not isinstance(stage, dict):
            continue
        name = str(stage.get("name", "unnamed"))
        if selected and name not in selected:
            continue
        if not bool(stage.get("enabled", True)):
            continue
        enabled_count += 1
        kind = str(stage.get("kind", "command"))
        if kind.startswith("upgrade"):
            stage_status = run_upgrade_stage(stage, manifest, context, args.execute, args.strict, args.trace)
        else:
            stage_status = run_command_stage(stage, manifest, context, args.execute, args.strict, args.trace)
        status = max(status, stage_status)
        if stage_status == STATUS_ERROR and args.strict:
            break

    if enabled_count == 0:
        print("[WARN] No enabled observation conversion stages were selected")
        status = max(status, STATUS_WARN)

    return status


def legacy_observations(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    observations = manifest.get("observations", [])
    if not isinstance(observations, list):
        raise ValueError("observations section must be a list")
    return [item for item in observations if isinstance(item, dict)]


def run_legacy(manifest: dict[str, Any], args: argparse.Namespace) -> int:
    converter = manifest.get("converter", {}) or {}
    env_name = converter.get("executable_env") if isinstance(converter, dict) else None
    converter_exe = os.environ.get(str(env_name), "").strip() if env_name else ""
    converter_exe = converter_exe or expand_text(converter.get("default_executable", "prepbufr_to_ioda.py"))
    observations = legacy_observations(manifest)
    selected = set(args.only)
    status = STATUS_OK

    for entry in observations:
        name = str(entry.get("name", "unnamed"))
        if selected and name not in selected:
            continue
        if not bool(entry.get("enabled", True)):
            continue
        source = expand_path(entry.get("source_file") or entry.get("prepbufr_file") or "")
        target = expand_path(entry.get("target_file") or entry.get("output_file") or "")
        context = {"name": name, "source_file": str(source), "prepbufr_file": str(source), "target_file": str(target), "output_file": str(target)}
        template = [converter_exe] + normalize_command(entry.get("converter_args")) + ["--input", "{source_file}", "--output", "{target_file}"]
        command = render_command(template, context)
        log_dir = expand_path((manifest.get("paths", {}) or {}).get("log_dir", "build/logs/obs_conversion"))
        log_file = log_dir / f"{name}.log"
        print(f"[INFO] observation={name}")
        print(f"[INFO]   command: {shlex.join(command)}")
        if not source.exists():
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] Missing source observation file for {name}: {source}")
            status = max(status, STATUS_ERROR if args.strict else STATUS_WARN)
            append_trace_stage(args.trace, {"name": name, "kind": "legacy", "status": "missing_source", "source": str(source), "source_exists": False, "command": command, "outputs": output_status([target])})
            continue
        if not args.execute:
            append_trace_stage(args.trace, {"name": name, "kind": "legacy", "status": "planned", "source": str(source), "source_exists": True, "command": command, "outputs": output_status([target])})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        rc = run_command(command, Path.cwd(), log_file)
        stage_status = "completed" if rc == 0 and target.exists() else "failed"
        status = max(status, STATUS_OK if stage_status == "completed" else STATUS_ERROR)
        append_trace_stage(args.trace, {"name": name, "kind": "legacy", "status": stage_status, "source": str(source), "source_exists": True, "command": command, "returncode": rc, "log_file": str(log_file), "outputs": output_status([target])})
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Observation conversion manifest YAML")
    parser.add_argument("--trace", type=Path, default=Path("build/rendered/provenance/obs_conversion.trace"))
    parser.add_argument("--execute", action="store_true", help="Run converter commands")
    parser.add_argument("--strict", action="store_true", help="Fail on missing inputs or failed outputs")
    parser.add_argument("--only", action="append", default=[], help="Run only selected stage or observation names")
    args = parser.parse_args()

    try:
        manifest = load_yaml(args.manifest)
    except Exception as exc:
        print(f"[ERROR] Failed to load observation conversion manifest: {exc}")
        return STATUS_ERROR

    print("[INFO] Observation conversion manifest")
    print(f"[INFO]   manifest : {args.manifest}")
    print(f"[INFO]   execute  : {args.execute}")
    print(f"[INFO]   strict   : {args.strict}")
    print(f"[INFO]   trace    : {args.trace}")

    write_trace_header(args.trace, args.manifest, args.execute, args.strict)

    try:
        if manifest.get("stages"):
            status = run_stages(manifest, args)
        else:
            status = run_legacy(manifest, args)
    except Exception as exc:
        print(f"[ERROR] Observation conversion failed before execution: {exc}")
        append_trace_final_products(args.trace, manifest)
        append_trace_result(args.trace, "failed", STATUS_ERROR)
        return STATUS_ERROR

    append_trace_final_products(args.trace, manifest)

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
