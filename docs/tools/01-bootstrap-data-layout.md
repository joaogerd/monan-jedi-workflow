# 01. bootstrap_data_layout.py

[Back to tools index](../tools.md) | Previous: none | Next: [audit_input_sources.py](02-audit-input-sources.md)

## Purpose

`bootstrap_data_layout.py` creates the directory structure expected by a MONAN-JEDI experiment from a data layout YAML file. It can also report whether declared expected files already exist.

## Context of use

Use this tool at the beginning of an experiment setup, before synchronizing, staging, or validating scientific inputs. It prepares the filesystem layout but does not create data files.

## Location

```text
tools/bootstrap_data_layout.py
```

## Prerequisites

- Python 3.
- PyYAML.
- A data layout YAML file with a top-level `data_layout` mapping.

## How to run

```bash
python tools/bootstrap_data_layout.py [layout] [--dry-run] [--check-files]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `layout` | Optional data layout YAML file. Defaults to `configs/experiments/3dvar_fgat/data_layout.example.yaml`. |
| `--dry-run` | Prints directory creation actions without creating directories. |
| `--check-files` | Fails if files listed under `expected_files` are missing. |

## Expected inputs

The layout file must contain `data_layout.root`, optionally `data_layout.directories`, and optionally `data_layout.expected_files`. Environment variables in the root are expanded.

## Outputs and effects

The tool creates directories under the configured data root unless `--dry-run` is used. It prints `[FOUND]`, `[WARN]`, or `[ERROR]` messages for expected files. It returns `0` on success and `2` when validation fails.

## Examples

Minimum execution:

```bash
python tools/bootstrap_data_layout.py
```

Dry-run with an explicit layout:

```bash
python tools/bootstrap_data_layout.py configs/experiments/3dvar_fgat/data_layout.yaml --dry-run
```

Check that expected files exist:

```bash
python tools/bootstrap_data_layout.py configs/experiments/3dvar_fgat/data_layout.yaml --check-files
```

## Common errors

- `Layout must contain data_layout mapping`: the YAML file does not have the expected top-level key.
- `data_layout.root is required`: the layout does not define the data root.
- `Expected file entry missing path`: an item in `expected_files` lacks a `path` field.

## Related tools

Run this before [`sync_input_sources.py`](03-sync-input-sources.md), [`stage_inputs.py`](06-stage-inputs.md), and [`validate_staged_inputs.py`](07-validate-staged-inputs.md).

[Back to tools index](../tools.md) | Previous: none | Next: [audit_input_sources.py](02-audit-input-sources.md)
