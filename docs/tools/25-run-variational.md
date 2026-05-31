# 25. run_variational.py

[Back to tools index](../tools.md) | Previous: [prepare_runtime.py](24-prepare-runtime.md) | Next: [create_github_repo_manual.sh](26-create-github-repo-manual.md)

## Purpose

`run_variational.py` builds and optionally runs the MPAS-JEDI variational command from a YAML configuration file.

## Context of use

Use this at the final execution stage. By default, it only prints the command. Real execution requires `--execute`.

## Location

```text
tools/run_variational.py
```

## Prerequisites

Python 3, PyYAML, a run configuration with `variational_run`, a rendered JEDI YAML file, and a valid executable path for real runs.

## How to run

```bash
python tools/run_variational.py config [--execute] [--strict] [--command-file FILE]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `config` | Run command YAML. |
| `--execute` | Executes the assembled command. |
| `--strict` | Fails if executable or YAML inputs are missing. |
| `--command-file` | Writes the assembled command to a file. |

## Inputs and outputs

The config may define executable, YAML path, MPI launcher, task count, extra arguments, environment variables, work directory, and log file. In execution mode, output goes to the configured log file.

## Examples

```bash
python tools/run_variational.py build/rendered/variational_run.yaml
```

```bash
python tools/run_variational.py build/rendered/variational_run.yaml --command-file build/run_command.sh
```

```bash
python tools/run_variational.py build/rendered/variational_run.yaml --strict --execute
```

## Common errors

- Missing `variational_run` mapping.
- Executable path unresolved or missing.
- JEDI YAML file missing.
- Subprocess returns a non-zero exit code.

## Related tools

Use after [`prepare_runtime.py`](24-prepare-runtime.md) and [`check_mpas_jedi_build.py`](23-check-mpas-jedi-build.md).

[Back to tools index](../tools.md) | Previous: [prepare_runtime.py](24-prepare-runtime.md) | Next: [create_github_repo_manual.sh](26-create-github-repo-manual.md)
