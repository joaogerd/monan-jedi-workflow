# 03. sync_input_sources.py

[Back to tools index](../tools.md) | Previous: [audit_input_sources.py](02-audit-input-sources.md) | Next: [check_external_input_root.py](04-check-external-input-root.md)

## Purpose

`sync_input_sources.py` synchronizes files declared in the input source registry into the external data tree. It creates either symbolic links or copies under the configured external root.

## Context of use

Use this after auditing source paths and before staging files into `MONAN_DATA_ROOT`. This tool builds the external input area from real source files.

## Location

```text
tools/sync_input_sources.py
```

## Prerequisites

- Python 3.
- PyYAML.
- Source files declared in the registry.
- A resolved external root from `input_sources.destinations.external_root` or `MONAN_EXTERNAL_DATA_ROOT`.

## How to run

```bash
python tools/sync_input_sources.py [registry] [--dry-run] [--copy]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `registry` | Optional input source registry. Defaults to `configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml`. |
| `--dry-run` | Prints planned actions without creating files or directories. |
| `--copy` | Copies files instead of creating symbolic links. Default action is linking. |

## Expected inputs

The registry must contain `input_sources.sources`. Each source should define `source_path` and `external_target`. Required entries fail when the source path is missing or unresolved during real execution.

## Outputs and effects

The tool creates directories under the external root and then links or copies files. Existing targets are preserved and are not replaced.

## Examples

Minimum execution:

```bash
python tools/sync_input_sources.py
```

Dry-run:

```bash
python tools/sync_input_sources.py configs/experiments/3dvar_fgat/input_sources.jaci.yaml --dry-run
```

Copy instead of linking:

```bash
python tools/sync_input_sources.py configs/experiments/3dvar_fgat/input_sources.jaci.yaml --copy
```

## Common errors

- `registry must contain input_sources mapping`: wrong YAML file or wrong root key.
- `external_root is missing or unresolved`: no usable external root was configured.
- `source_path has unresolved variable`: an environment variable in `source_path` was not defined.
- `source file not found`: the source path does not point to a regular file.

## Related tools

Usually follows [`audit_input_sources.py`](02-audit-input-sources.md) and precedes [`check_external_input_root.py`](04-check-external-input-root.md) and [`stage_inputs.py`](06-stage-inputs.md).

[Back to tools index](../tools.md) | Previous: [audit_input_sources.py](02-audit-input-sources.md) | Next: [check_external_input_root.py](04-check-external-input-root.md)
