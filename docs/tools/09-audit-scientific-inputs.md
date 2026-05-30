# 09. audit_scientific_inputs.py

[Back to tools index](../tools.md) | Previous: [validate_file_formats.py](08-validate-file-formats.md) | Next: [check_ioda_inventory.py](10-check-ioda-inventory.md)

## Purpose

`audit_scientific_inputs.py` audits the scientific input checklist. It reports the experiment, cycle, data root, input kind, validation status, and whether each declared target exists.

## Context of use

Use this after staging and basic format validation. It gives a human-readable view of the scientific checklist and can enforce validation status in strict mode.

## Location

```text
tools/audit_scientific_inputs.py
```

## Prerequisites

Python 3, PyYAML, and a checklist file with top-level `scientific_input_checklist`.

## How to run

```bash
python tools/audit_scientific_inputs.py [checklist] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `checklist` | Scientific checklist file. Defaults to `configs/experiments/3dvar_fgat/scientific_input_checklist.yaml`. |
| `--strict` | Fails if required inputs are not marked as `validated_basic` or `validated_scientific`. |

## Inputs and outputs

The tool reads checklist metadata and checks whether declared target files exist under the configured data root. It does not open or validate scientific contents.

## Examples

```bash
python tools/audit_scientific_inputs.py
```

```bash
python tools/audit_scientific_inputs.py configs/experiments/3dvar_fgat/scientific_input_checklist.yaml --strict
```

## Common errors

- Missing `scientific_input_checklist` mapping.
- `inputs` is not a list.
- Required input is not validated in strict mode.

## Related tools

Use after [`validate_file_formats.py`](08-validate-file-formats.md) and with [`check_input_consistency.py`](05-check-input-consistency.md).

[Back to tools index](../tools.md) | Previous: [validate_file_formats.py](08-validate-file-formats.md) | Next: [check_ioda_inventory.py](10-check-ioda-inventory.md)
