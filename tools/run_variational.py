#!/usr/bin/env python3
"""Build and optionally execute a JEDI-MPAS variational command.

This wrapper assembles the command line used to run ``mpasjedi_variational.x``
from a small YAML configuration file. It supports MPI launchers, task-count
flags, additional executable arguments, environment overrides, command-file
export, and optional real execution.

The tool is conservative by design. By default it runs in dry-run mode and only
prints the command that would be executed. Real execution requires ``--execute``.
This reduces the risk of accidentally launching an expensive HPC job while a
workflow is still being rendered, documented, or validated.

Examples
--------
Print the variational command without executing it::

    $ python tools/run_variational.py build/rendered/variational_run.yaml

Write the assembled command to a shell-readable file::

    $ python tools/run_variational.py build/rendered/variational_run.yaml --command-file build/run_command.sh

Validate required inputs and execute the command::

    $ python tools/run_variational.py build/rendered/variational_run.yaml --strict --execute
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
    """Expand shell-style environment variables in a string.

    Parameters
    ----------
    value : str
        Text that may contain variables such as ``${MPASJEDI_VARIATIONAL_EXE}``
        or ``${MPI_TASKS_FLAG}``.

    Returns
    -------
    str
        Expanded text according to the current process environment.

    Raises
    ------
    TypeError
        If ``value`` is not a string.

    Notes
    -----
    Undefined variables remain unchanged. Input validation later reports
    unresolved executable paths as warnings or errors depending on the selected
    mode.

    See Also
    --------
    os.path.expandvars : Expand environment variables in strings.
    validate_inputs : Check expanded executable and YAML paths.

    Examples
    --------
    >>> expand("/tmp/${UNDEFINED_MONAN_EXE}")
    '/tmp/${UNDEFINED_MONAN_EXE}'
    """
    return os.path.expandvars(value)


def load_config(path: Path) -> dict[str, Any]:
    """Load and validate a variational run configuration.

    Parameters
    ----------
    path : pathlib.Path
        Path to the YAML file containing a top-level ``variational_run`` mapping.

    Returns
    -------
    dict of str to Any
        The ``variational_run`` configuration mapping.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the YAML document does not contain ``variational_run``.
    TypeError
        If ``variational_run`` exists but is not a mapping.
    yaml.YAMLError
        If the file is not valid YAML.
    OSError
        If the file cannot be read.

    Notes
    -----
    The configuration is expected to declare at least ``executable`` and ``yaml``.
    Optional keys include ``mpi_launcher``, ``mpi_tasks``, ``mpi_tasks_flag``,
    ``extra_args``, ``environment``, ``work_dir``, and ``log_file``.

    See Also
    --------
    build_command : Convert the configuration into a subprocess command list.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("variational_run.yaml")
    >>> _ = path.write_text("variational_run:\n  executable: mpasjedi_variational.x\n  yaml: config.yaml\n", encoding="utf-8")
    >>> load_config(path)["yaml"]
    'config.yaml'
    >>> path.unlink()
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "variational_run" not in data:
        raise ValueError(f"Configuration must contain a 'variational_run' mapping: {path}")

    cfg = data["variational_run"]
    if not isinstance(cfg, dict):
        raise TypeError("variational_run must be a mapping")

    return cfg


def build_command(cfg: dict[str, Any]) -> list[str]:
    """Build the variational command as a subprocess argument list.

    Parameters
    ----------
    cfg : dict of str to Any
        Variational run configuration loaded from YAML.

    Returns
    -------
    list of str
        Command suitable for ``subprocess.run`` without ``shell=True``.

    Raises
    ------
    KeyError
        If required configuration keys ``executable`` or ``yaml`` are missing.
    ValueError
        If ``mpi_tasks`` cannot be converted to an integer.

    Notes
    -----
    ``mpi_launcher`` is parsed with ``shlex.split`` so values such as
    ``"mpiexec --cpu-bind depth"`` are handled as multiple command arguments.
    The executable and JEDI YAML file are then appended in the order expected by
    MPAS-JEDI variational applications.

    See Also
    --------
    shlex.split : Split launcher text into shell-like arguments.
    write_command_file : Write a shell-escaped representation of the command.

    Examples
    --------
    >>> cfg = {"executable": "mpasjedi_variational.x", "yaml": "3dvar.yaml"}
    >>> build_command(cfg)
    ['mpasjedi_variational.x', '3dvar.yaml']
    >>> cfg = {"mpi_launcher": "mpiexec", "mpi_tasks": 2, "executable": "mpasjedi_variational.x", "yaml": "3dvar.yaml"}
    >>> build_command(cfg)
    ['mpiexec', '-n', '2', 'mpasjedi_variational.x', '3dvar.yaml']
    """
    executable = expand(str(cfg["executable"]))
    mpi_launcher = expand(str(cfg.get("mpi_launcher", ""))).strip()
    mpi_tasks = int(cfg.get("mpi_tasks", 1))
    mpi_tasks_flag = expand(str(cfg.get("mpi_tasks_flag", os.environ.get("MPI_TASKS_FLAG", "-n")))).strip()
    yaml_file = expand(str(cfg["yaml"]))
    extra_args = [str(item) for item in cfg.get("extra_args", [])]

    if mpi_launcher:
        launcher_parts = shlex.split(mpi_launcher)
        if mpi_tasks_flag:
            cmd = launcher_parts + [mpi_tasks_flag, str(mpi_tasks), executable, yaml_file]
        else:
            cmd = launcher_parts + [str(mpi_tasks), executable, yaml_file]
    else:
        cmd = [executable, yaml_file]

    cmd.extend(extra_args)
    return cmd


def validate_inputs(cfg: dict[str, Any], *, strict: bool) -> bool:
    """Validate the executable and rendered JEDI YAML paths.

    Parameters
    ----------
    cfg : dict of str to Any
        Variational run configuration containing ``executable`` and ``yaml``.
    strict : bool
        If ``True``, missing or unresolved inputs cause the caller to fail.

    Returns
    -------
    bool
        ``True`` when required paths look usable. ``False`` when an unresolved or
        missing executable/YAML path is detected.

    Raises
    ------
    KeyError
        If required keys ``executable`` or ``yaml`` are missing.

    Notes
    -----
    This function only checks path existence and unresolved variables. It does
    not verify that the executable is scientifically compatible with the YAML
    file or that the YAML file is a valid JEDI application configuration.

    See Also
    --------
    expand : Expand variables before checking paths.
    build_command : Build the command that will use these inputs.

    Examples
    --------
    >>> validate_inputs({"executable": "${MISSING_EXE}", "yaml": "missing.yaml"}, strict=False)
    [WARN] Executable still contains unresolved variable: ${MISSING_EXE}
    [WARN] JEDI YAML not found: missing.yaml
    True
    """
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
    """Write a shell-escaped command line to a text file.

    Parameters
    ----------
    command : list of str
        Command arguments to write.
    output : pathlib.Path
        Output file path.

    Returns
    -------
    None
        The command is written to disk with a trailing newline.

    Raises
    ------
    OSError
        If the output directory cannot be created or the file cannot be written.

    Notes
    -----
    Each command component is escaped with ``shlex.quote`` so the resulting file
    can be inspected or pasted into a shell with minimal ambiguity.

    See Also
    --------
    shlex.quote : Shell-escape individual command arguments.
    build_command : Build the command written by this function.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("command.txt")
    >>> write_command_file(["mpiexec", "-n", "2", "run.x"], path)
    >>> path.read_text(encoding="utf-8")
    'mpiexec -n 2 run.x\n'
    >>> path.unlink()
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(" ".join(shlex.quote(part) for part in command) + "\n", encoding="utf-8")


def main() -> int:
    """Run the variational command wrapper.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` in dry-run mode when command assembly
        succeeds. In execution mode, returns the subprocess return code. Returns
        ``2`` when strict validation fails before execution.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    yaml.YAMLError
        If the configuration file is invalid YAML.
    OSError
        If command-file writing or log-file creation fails.
    subprocess.SubprocessError
        If process execution fails before a return code is available.

    Notes
    -----
    Environment variables declared under ``variational_run.environment`` are
    applied only to the child process environment. They do not modify the parent
    shell environment.

    See Also
    --------
    load_config : Load the YAML run configuration.
    build_command : Assemble the command list.
    validate_inputs : Check executable and YAML paths.
    write_command_file : Save the assembled command.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
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
