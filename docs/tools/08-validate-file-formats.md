# 08. validate_file_formats.py

[Back to tools index](../tools.md) | Previous: [validate_staged_inputs.py](07-validate-staged-inputs.md) | Next: [audit_scientific_inputs.py](09-audit-scientific-inputs.md)

## Purpose

`validate_file_formats.py` checks basic file format conditions for staged inputs: file presence, non-empty size, extension compatibility with the declared kind, and optional open checks for NetCDF or HDF5 files when Python libraries are available.

## Context of use

Run this after the staged input files exist and before running scientific or JEDI-specific validation.

## Location

```text
tools/validate_file_formats.py
```

## Prerequisites

Python 3, PyYAML, and a data layout file. NetCDF/HDF5 Python libraries are optional.

## How to run

```bash
python tools/validate_file_formats.py [layout] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `layout` | Data layout file. Defaults to the 3DVar-FGAT example layout. |
| `--strict` | Turns missing or invalid required files into failures. |

## Inputs and outputs

The tool reads `data_layout.expected_files` and resolves paths under `data_layout.data_root` or `MONAN_DATA_ROOT`. It prints validation messages and returns `2` when strict validation fails.

## Examples

```bash
python tools/validate_file_formats.py
```

```bash
python tools/validate_file_formats.py configs/experiments/3dvar_fgat/data_layout.yaml --strict
```

## Common errors

- Missing or unresolved data root.
- Missing file.
- Empty file.
- Extension does not match the declared kind.
- A parser cannot open a declared NetCDF or HDF5 file.

## Related tools

Use after [`validate_staged_inputs.py`](07-validate-staged-inputs.md) and before [`validate_ioda_structure.py`](11-validate-ioda-structure.md) when working with IODA files.

[Back to tools index](../tools.md) | Previous: [validate_staged_inputs.py](07-validate-staged-inputs.md) | Next: [audit_scientific_inputs.py](09-audit-scientific-inputs.md)
