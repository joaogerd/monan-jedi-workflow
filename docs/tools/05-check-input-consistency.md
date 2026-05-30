# 05. check_input_consistency.py

[Back to tools index](../tools.md) | Previous: [check_external_input_root.py](04-check-external-input-root.md) | Next: [stage_inputs.py](06-stage-inputs.md)

## Purpose

`check_input_consistency.py` compares three metadata files: the input source registry, the staging manifest, and the scientific input checklist. It verifies that the same logical inputs appear consistently across them.

## Context of use

Use this before staging or validating data. It catches metadata drift, such as an input declared in the source registry but missing from staging or from the scientific checklist.

## Location

```text
tools/check_input_consistency.py
```

## Prerequisites

- Python 3 and PyYAML.
- Source registry with `input_sources.sources`.
- Staging manifest with `input_staging.files`.
- Checklist with `scientific_input_checklist.inputs`.

## How to run

```bash
python tools/check_input_consistency.py [--sources FILE] [--staging FILE] [--checklist FILE]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--sources` | Input source registry. |
| `--staging` | Input staging manifest. |
| `--checklist` | Scientific input checklist. |

## Inputs and outputs

The tool reads YAML metadata only. It does not inspect actual scientific files. It prints `[ERROR]` for missing, extra, duplicated, or inconsistent entries and returns `2` if any inconsistency is found.

## Examples

```bash
python tools/check_input_consistency.py
```

```bash
python tools/check_input_consistency.py \
  --sources configs/experiments/3dvar_fgat/input_sources.yaml \
  --staging configs/experiments/3dvar_fgat/staging.yaml \
  --checklist configs/experiments/3dvar_fgat/scientific_input_checklist.yaml
```

## Common errors

- Source missing from staging manifest.
- Source missing from scientific checklist.
- Target mismatch between source, staging, and checklist.
- Required flag mismatch.
- Kind mismatch.

## Related tools

Use before [`stage_inputs.py`](06-stage-inputs.md), [`audit_scientific_inputs.py`](09-audit-scientific-inputs.md), and [`validate_staged_inputs.py`](07-validate-staged-inputs.md).

[Back to tools index](../tools.md) | Previous: [check_external_input_root.py](04-check-external-input-root.md) | Next: [stage_inputs.py](06-stage-inputs.md)
