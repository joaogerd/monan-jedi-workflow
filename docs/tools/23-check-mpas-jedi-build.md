# 23. check_mpas_jedi_build.py

[Back to tools index](../tools.md) | Previous: [find_mpas_jedi_build.py](22-find-mpas-jedi-build.md) | Next: [prepare_runtime.py](24-prepare-runtime.md)

## Purpose

`check_mpas_jedi_build.py` validates an MPAS-JEDI build discovery manifest. It checks the build root, required executables, optional executables, and expected commands.

## Context of use

Run this after selecting a build directory and before preparing runtime files or executing the variational command.

## Location

```text
tools/check_mpas_jedi_build.py
```

## Prerequisites

Python 3, PyYAML, and a build manifest with top-level `mpas_jedi_build`.

## How to run

```bash
python tools/check_mpas_jedi_build.py [manifest] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `manifest` | Build manifest. Defaults to `configs/sites/jaci/mpas_jedi_build.example.yaml`. |
| `--strict` | Fails if required files or commands are missing. |

## Inputs and outputs

The tool expands environment variables, checks build root existence, verifies executable paths, checks executable permissions, and searches expected commands in `PATH`.

## Examples

```bash
python tools/check_mpas_jedi_build.py
```

```bash
python tools/check_mpas_jedi_build.py configs/sites/jaci/mpas_jedi_build.yaml --strict
```

## Common errors

- Manifest lacks `mpas_jedi_build`.
- Build root is unresolved or not a directory.
- Required executable is missing or not executable.
- Expected command is not found in `PATH`.

## Related tools

Use after [`find_mpas_jedi_build.py`](22-find-mpas-jedi-build.md) and before [`run_variational.py`](25-run-variational.md).

[Back to tools index](../tools.md) | Previous: [find_mpas_jedi_build.py](22-find-mpas-jedi-build.md) | Next: [prepare_runtime.py](24-prepare-runtime.md)
