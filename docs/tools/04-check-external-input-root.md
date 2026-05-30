# 04. check_external_input_root.py

[Back to tools index](../tools.md) | Previous: [sync_input_sources.py](03-sync-input-sources.md) | Next: [check_input_consistency.py](05-check-input-consistency.md)

## Purpose

`check_external_input_root.py` verifies the external input root used by the staging workflow and reports the parent directories referenced by the staging manifest.

## Context of use

Use this before staging data into `MONAN_DATA_ROOT`. It helps confirm that the external input area exists and that the manifest points to plausible source locations.

## Location

```text
tools/check_external_input_root.py
```

## Prerequisites

- Python 3.
- PyYAML.
- A staging manifest with `input_staging.files`.
- The environment variable used by the workflow for the external data root.

## How to run

```bash
python tools/check_external_input_root.py [manifest] [--allow-missing]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `manifest` | Optional staging manifest. Defaults to `configs/experiments/3dvar_fgat/staging.example.yaml`. |
| `--allow-missing` | Treats a missing external root as a warning instead of an error. |

## Inputs and outputs

The tool reads the staging manifest and environment. It does not modify files. It prints whether the root exists, whether it is a directory, and whether source parent directories are present.

## Examples

```bash
python tools/check_external_input_root.py
```

```bash
python tools/check_external_input_root.py configs/experiments/3dvar_fgat/staging.yaml --allow-missing
```

## Common errors

- Missing root environment variable: the external input root was not configured.
- Root not found: the configured path does not exist.
- Root is not a directory: the path exists but is not usable as a data root.
- Invalid `input_staging.files`: the manifest structure is wrong.

## Related tools

Use with [`sync_input_sources.py`](03-sync-input-sources.md), [`check_input_consistency.py`](05-check-input-consistency.md), and [`stage_inputs.py`](06-stage-inputs.md).

[Back to tools index](../tools.md) | Previous: [sync_input_sources.py](03-sync-input-sources.md) | Next: [check_input_consistency.py](05-check-input-consistency.md)
