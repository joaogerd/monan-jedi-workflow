# 10. check_ioda_inventory.py

[Back to tools index](../tools.md) | Previous: [audit_scientific_inputs.py](09-audit-scientific-inputs.md) | Next: [validate_ioda_structure.py](11-validate-ioda-structure.md)

## Purpose

`check_ioda_inventory.py` checks whether the IODA inventory, observer manifest, and observer metadata agree with each other.

## Context of use

Run this before observer rendering or IODA structure validation. It confirms that enabled observers have inventory entries and metadata records.

## Location

```text
tools/check_ioda_inventory.py
```

## Prerequisites

Python 3, PyYAML, an IODA inventory, an observer manifest, and observer metadata.

## How to run

```bash
python tools/check_ioda_inventory.py [--inventory FILE] [--manifest FILE] [--metadata FILE] [--strict-files]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--inventory` | IODA inventory file. |
| `--manifest` | Observer manifest file. |
| `--metadata` | Observer metadata file. |
| `--strict-files` | Requires required IODA files to exist. |

## Inputs and outputs

The tool reads YAML metadata and prints validation messages for each observer. It checks enabled observers, expected groups, declared paths, and optionally file presence.

## Examples

```bash
python tools/check_ioda_inventory.py
```

```bash
python tools/check_ioda_inventory.py --strict-files
```

## Common errors

- Missing `ioda_inventory`, `observers`, or `observer_plugs` root section.
- Observer in inventory is not enabled.
- Missing observer metadata.
- Expected group mismatch.
- Enabled observer missing from the inventory.

## Related tools

Use before [`validate_ioda_structure.py`](11-validate-ioda-structure.md) and [`validate_jedi_observer_config.py`](15-validate-jedi-observer-config.md).

[Back to tools index](../tools.md) | Previous: [audit_scientific_inputs.py](09-audit-scientific-inputs.md) | Next: [validate_ioda_structure.py](11-validate-ioda-structure.md)
