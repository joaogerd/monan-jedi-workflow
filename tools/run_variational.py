#!/usr/bin/env python3
"""Build and optionally execute a JEDI-MPAS variational command.

This wrapper is intentionally conservative. By default it runs in dry-run mode and only prints the
command that would be executed. Real execution requires `--execute`.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml


def expand(value: str) -> str:
    """Expand environment variables in a string."""
    return os.path.expandvars(value)


def load_config(path: Path) -> dict[str, Any]:
    """Load run command configuration."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "variational_run" not in data:
        raise ValueError(f"Configuration must contain a 'variational_run' mapping: {path}")
    cfg = data["variational_run"]
    if not isinstance(cfg, dict):
        raise TypeError("variational_run must be a mapping")
    return cfg


def build_command(cfg: dict[str, Any]) -> list[str]:
    """Build the variational command as a list suitable for subprocess."""
    executable = expand(str(cfg["executable"]))
    mpi_launcher = expand(str(cfg.get("mpi_launcher", ""))).strip()
    mpi_tasks = int(cfg.get("mpi_tasks", 1))
    yaml_file = expand(str(cfg["yaml"]))
    extra_args = [str(item) for item in cfg.get("extra_args", [])]

    if mpi_launcher:
        cmd = shlex.split(mpi_launcher) + ["-n", str(mpi_tasks), executable, yaml_file]
    else:
        cmd = [executable, yaml_file]
    cmd.extend(extra_args)
    return cmd


def validate_inputs(cfg: dict[str, Any], *, strict: bool) -> bool:
    """Validate executable and YAML paths."""
    ok = True
    executable = Path(expand(str(cfg["executable"])))
    yaml_file = Path(expand(str(cfg["yaml"])))

    if "$" in str(executable):
        print(f"[WARN] Executable still contains unresolved variable: {executable}")
        ok = False
    elif not executable.exists():
        print(f"[WARN] Executable not found: {executable}")
        ok = False

    if not yaml_file.exists():
        print(f"[WARN] JEDI YAML not found: {yaml_file}")
        ok = False

    if strict and not ok:
        return False
    return True


def write_command_file(command: list[str], output: Path) -> None:
    """Write a shell-escaped command file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(" ".join(shlex.quote(part) for part in command) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or execute a JEDI-MPAS variational command.")
    parser.add_argument("config", type=Path, help="Run command YAML")
    parser.add_argument("--execute", action="store_true", help="Execute command. Default is dry-run.")
    parser.add_argument("--strict", action="store_true", help="Fail if executable/YAML are missing")
    parser.add_argument("--command-file", type=Path, help="Write assembled command to this file")
    args = parser.parse_args()

    cfg = load_config(args.config)
    command = build_command(cfg)

    print("[INFO] Variational command:")
    print("  " + " ".join(shlex.quote(part) for part in command))

    if args.command_file:
        write_command_file(command, args.command_file)
        print(f"[INFO] Command written to {args.command_file}")

    valid = validate_inputs(cfg, strict=args.strict or args.execute)
    if (args.strict or args.execute) and not valid:
        print("[ERROR] Required inputs are not valid")
        return 2

    env = os.environ.copy()
    for key, value in cfg.get("environment", {}).items():
        env[str(key)] = expand(str(value))

    work_dir = Path(expand(str(cfg.get("work_dir", "."))))

    if not args.execute:
        print("[INFO] Dry-run mode. Use --execute to run the command.")
        return 0

    log_file = work_dir / str(cfg.get("log_file", "mpasjedi_variational.log"))
    log_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Executing in {work_dir}")
    print(f"[INFO] Log file: {log_file}")

    with log_file.open("w", encoding="utf-8") as stream:
        proc = subprocess.run(command, cwd=work_dir, env=env, stdout=stream, stderr=subprocess.STDOUT)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
