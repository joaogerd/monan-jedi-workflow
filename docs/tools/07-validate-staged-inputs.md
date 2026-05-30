# 07. validate_staged_inputs.py

[Back to tools index](../tools.md) | Previous: [stage_inputs.py](06-stage-inputs.md) | Next: [validate_file_formats.py](08-validate-file-formats.md)

## Purpose

`validate_staged_inputs.py` checks whether expected staged input files exist, are regular files, are non-empty, and have a broad recognizable kind.

## Context of use

Run this after staging inputs and before deeper format or scientific checks. It is a lightweight pre-flight validator.

## Location

```text
tools/validate_staged_inputs.py
```

## Prerequisites

- Python 3 and PyYAML.
- A data layout YAML file with `data_layout.root` and `data_layout.expected_files`.

## How to run

```bash
python tools/validate_staged_inputs.py [layout] [--allow-missing]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `layout` | Data layout file. Defaults to `configs/experiments/3dvar_fgat/data_layout.example.yaml`. |
| `--allow-missing` | Reports missing files as warnings instead of errors. |

## Inputs and outputs

The tool reads expected file paths from the layout and checks files under the layout root. It prints file size, inferred kind, and requirement context. It does not open NetCDF or HDF5 internals.

## Examples

```bash
python tools/validate_staged_inputs.py
```

```bash
python tools/validate_staged_inputs.py configs/experiments/3dvar_fgat/data_layout.yaml --allow-missing
```

## Common errors

- Missing `data_layout` mapping.
- `expected_files` is not a list.
- Expected file entry without `path`.
- File is missing, empty, or not a regular file.

## Related tools

Usually follows [`stage_inputs.py`](06-stage-inputs.md) and precedes [`validate_file_formats.py`](08-validate-file-formats.md).

[Back to tools index](../tools.md) | Previous: [stage_inputs.py](06-stage-inputs.md) | Next: [validate_file_formats.py](08-validate-file-formats.md)
