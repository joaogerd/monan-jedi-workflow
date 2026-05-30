# 06. stage_inputs.py

[Back to tools index](../tools.md) | Previous: [check_input_consistency.py](05-check-input-consistency.md) | Next: [validate_staged_inputs.py](07-validate-staged-inputs.md)

## Purpose

`stage_inputs.py` stages external scientific inputs into the workflow data root. It reads a staging manifest and creates either copies or symbolic links for each declared file.

## Context of use

Run this after the external input area is available and before validating staged files. It prepares the data tree consumed by the rendered MONAN-JEDI experiment.

## Location

```text
tools/stage_inputs.py
```

## Prerequisites

- Python 3 and PyYAML.
- A manifest with top-level `input_staging`.
- Existing source files, unless running in `--dry-run` mode or checking optional inputs.

## How to run

```bash
python tools/stage_inputs.py [manifest] [--dry-run] [--copy] [--link] [--force]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `manifest` | Staging manifest. Defaults to `configs/experiments/3dvar_fgat/staging.example.yaml`. |
| `--dry-run` | Shows planned actions without changing files. |
| `--copy` | Forces copy mode. |
| `--link` | Forces symbolic-link mode. |
| `--force` | Removes existing targets before staging. |

## Inputs and outputs

The manifest provides `data_root`, `default_action`, and a `files` list. Each file entry needs a `source` and a `target`. The tool creates parent directories and then links or copies files. Existing targets are preserved unless `--force` is used.

## Examples

```bash
python tools/stage_inputs.py --dry-run
```

```bash
python tools/stage_inputs.py configs/experiments/3dvar_fgat/staging.yaml --link
```

```bash
python tools/stage_inputs.py configs/experiments/3dvar_fgat/staging.yaml --copy --force
```

## Common errors

- Invalid entry: missing `source` or `target`.
- Unresolved variable in `source`.
- Source file not found.
- Unsupported action; only `copy` and `link` are supported.

## Related tools

Use after [`sync_input_sources.py`](03-sync-input-sources.md) and before [`validate_staged_inputs.py`](07-validate-staged-inputs.md).

[Back to tools index](../tools.md) | Previous: [check_input_consistency.py](05-check-input-consistency.md) | Next: [validate_staged_inputs.py](07-validate-staged-inputs.md)
