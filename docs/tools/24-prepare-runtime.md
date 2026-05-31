# 24. prepare_runtime.py

[Back to tools index](../tools.md) | Previous: [check_mpas_jedi_build.py](23-check-mpas-jedi-build.md) | Next: [run_variational.py](25-run-variational.md)

## Purpose

`prepare_runtime.py` creates a MONAN-JEDI runtime directory and applies file link or copy actions declared in a runtime manifest.

## Context of use

Run this after rendering workflow products and validating inputs. It prepares the directory layout used by the actual variational execution.

## Location

```text
tools/prepare_runtime.py
```

## Prerequisites

Python 3, PyYAML, and a runtime manifest with top-level `runtime`.

## How to run

```bash
python tools/prepare_runtime.py manifest [--work-dir DIR] [--dry-run] [--copy] [--force]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `manifest` | Runtime manifest YAML. |
| `--work-dir` | Overrides `runtime.work_dir`. |
| `--dry-run` | Prints planned actions without creating directories or links. |
| `--copy` | Copies files instead of creating symbolic links. |
| `--force` | Replaces existing targets. |

## Inputs and outputs

The tool reads `runtime.directories`, `runtime.links`, and optionally `runtime.rendered`. It creates directories and links or copies declared files. Missing required files fail real execution.

## Examples

```bash
python tools/prepare_runtime.py build/rendered/runtime.yaml --dry-run
```

```bash
python tools/prepare_runtime.py build/rendered/runtime.yaml --copy --force
```

## Common errors

- Manifest lacks `runtime`.
- `runtime` is not a mapping.
- Required source file is missing.
- Existing target cannot be removed when `--force` is used.

## Related tools

Use before [`run_variational.py`](25-run-variational.md) and after [`validate_experiment.py`](18-validate-experiment.md).

[Back to tools index](../tools.md) | Previous: [check_mpas_jedi_build.py](23-check-mpas-jedi-build.md) | Next: [run_variational.py](25-run-variational.md)
