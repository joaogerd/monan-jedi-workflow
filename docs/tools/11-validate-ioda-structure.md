# 11. validate_ioda_structure.py

[Back to tools index](../tools.md) | Previous: [check_ioda_inventory.py](10-check-ioda-inventory.md) | Next: [check_observer_manifest.py](12-check-observer-manifest.md)

## Purpose

`validate_ioda_structure.py` performs basic structural checks on IODA/HDF5 observation files declared in the inventory.

## Context of use

Run this after IODA files are staged and the IODA inventory has been checked. It is useful before launching JEDI because missing IODA groups or missing `ObsValue` variables can cause runtime failures.

## Location

```text
tools/validate_ioda_structure.py
```

## Prerequisites

Python 3, PyYAML, and staged observation files. The `h5py` package is optional; without it, the tool only checks file existence and size.

## How to run

```bash
python tools/validate_ioda_structure.py [--inventory FILE] [--manifest FILE] [--data-root ROOT] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--inventory` | IODA inventory file. |
| `--manifest` | Observer manifest used to locate observer plug templates. |
| `--data-root` | Root used to resolve relative IODA paths. Defaults to `MONAN_DATA_ROOT`. |
| `--strict` | Fails on missing files, missing groups, or missing expected variables. |

## Inputs and outputs

The tool reads the inventory and observer manifest. When `h5py` is available, it reports root groups, common IODA groups, and variables found under `ObsValue`.

## Examples

```bash
python tools/validate_ioda_structure.py
```

```bash
python tools/validate_ioda_structure.py --data-root /data/monan --strict
```

## Common errors

- Missing or unresolved data root.
- Missing IODA file.
- Empty IODA file.
- Missing common groups such as `MetaData`, `ObsValue`, `ObsError`, or `PreQC`.
- Expected simulated variables not found under `ObsValue`.

## Related tools

Use after [`check_ioda_inventory.py`](10-check-ioda-inventory.md) and before [`validate_jedi_observer_config.py`](15-validate-jedi-observer-config.md).

[Back to tools index](../tools.md) | Previous: [check_ioda_inventory.py](10-check-ioda-inventory.md) | Next: [check_observer_manifest.py](12-check-observer-manifest.md)
