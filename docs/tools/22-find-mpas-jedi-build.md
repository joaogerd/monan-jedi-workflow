# 22. find_mpas_jedi_build.py

[Back to tools index](../tools.md) | Previous: [validate_saber_inputs.py](21-validate-saber-inputs.md) | Next: [check_mpas_jedi_build.py](23-check-mpas-jedi-build.md)

## Purpose

`find_mpas_jedi_build.py` searches selected filesystem roots for candidate MPAS-JEDI build directories and reports whether they contain useful executables.

## Context of use

Run this on an HPC filesystem when the correct MPAS-JEDI build location is unknown or when preparing site environment values.

## Location

```text
tools/find_mpas_jedi_build.py
```

## Prerequisites

Python 3 and access to candidate build directories. No YAML input is required.

## How to run

```bash
python tools/find_mpas_jedi_build.py [roots...] [--max-depth N] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `roots` | Optional search roots. If omitted, MONAN/JACI-related environment roots are used. |
| `--max-depth` | Maximum directory depth per root. Default is `5`. |
| `--strict` | Fails if no 3DVar-capable build is found. |

## Inputs and outputs

The tool scans directories and reports candidates containing files such as `mpasjedi_variational.x`, `mpas_atmosphere`, and `mpasjedi_hofx3d.x` under `bin/`. For usable builds, it prints suggested environment exports.

## Examples

```bash
python tools/find_mpas_jedi_build.py
```

```bash
python tools/find_mpas_jedi_build.py /p/projetos/monan_das/joao.gerd/projects --max-depth 4 --strict
```

## Common errors

- No roots provided and no known environment roots found.
- No build candidates found.
- Candidates exist but none contain `mpasjedi_variational.x` in strict mode.

## Related tools

Use before [`check_mpas_jedi_build.py`](23-check-mpas-jedi-build.md), [`prepare_runtime.py`](24-prepare-runtime.md), and [`run_variational.py`](25-run-variational.md).

[Back to tools index](../tools.md) | Previous: [validate_saber_inputs.py](21-validate-saber-inputs.md) | Next: [check_mpas_jedi_build.py](23-check-mpas-jedi-build.md)
