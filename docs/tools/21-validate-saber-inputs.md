# 21. validate_saber_inputs.py

[Back to tools index](../tools.md) | Previous: [validate_mpas_background.py](20-validate-mpas-background.md) | Next: [find_mpas_jedi_build.py](22-find-mpas-jedi-build.md)

## Purpose

`validate_saber_inputs.py` checks SABER/BUMP covariance paths declared in the render context.

## Context of use

Run this before executing the variational application. It verifies that the standard-deviation file, NICAS directory, and vertical-balance directory are resolved and present when strict mode is used.

## Location

```text
tools/validate_saber_inputs.py
```

## Prerequisites

Python 3, PyYAML, and a render context containing a `jedi` mapping.

## How to run

```bash
python tools/validate_saber_inputs.py [--render-context FILE] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--render-context` | Render context YAML. Defaults to the 3DVar-FGAT example context. |
| `--strict` | Fails when SABER/BUMP paths are missing or unresolved. |

## Inputs and outputs

The tool reads `bump_cov_stddev_file`, `bump_cov_dir`, and `bump_cov_vbal_dir` from the `jedi` mapping. It prints each resolved path and warnings or errors for missing paths.

## Examples

```bash
python tools/validate_saber_inputs.py
```

```bash
python tools/validate_saber_inputs.py --render-context configs/experiments/3dvar_fgat/render_context.yaml --strict
```

## Common errors

- Render context has no valid `jedi` mapping.
- SABER path is empty or unresolved.
- SABER path does not exist in strict mode.

## Related tools

Use with [`validate_mpas_background.py`](20-validate-mpas-background.md) before [`run_variational.py`](25-run-variational.md).

[Back to tools index](../tools.md) | Previous: [validate_mpas_background.py](20-validate-mpas-background.md) | Next: [find_mpas_jedi_build.py](22-find-mpas-jedi-build.md)
