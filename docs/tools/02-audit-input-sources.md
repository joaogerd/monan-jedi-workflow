# 02. audit_input_sources.py

[Back to tools index](../tools.md) | Previous: [bootstrap_data_layout.py](01-bootstrap-data-layout.md) | Next: [sync_input_sources.py](03-sync-input-sources.md)

## Purpose

`audit_input_sources.py` audits the input source registry. It reports each declared source, whether it is required, its discovery status, the expanded source path, and whether that file exists.

## Context of use

Use this tool before synchronizing inputs into the external data tree. It helps verify that the registry points to real files and that MPAS-JEDI build metadata is present when declared.

## Location

```text
tools/audit_input_sources.py
```

## Prerequisites

- Python 3.
- PyYAML.
- An input source registry with top-level `input_sources`.

## How to run

```bash
python tools/audit_input_sources.py [registry] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `registry` | Optional registry YAML. Defaults to `configs/experiments/3dvar_fgat/input_sources.example.yaml`. |
| `--strict` | Fails if required source files, the MPAS-JEDI build root, or the variational executable are missing. |

## Expected inputs

The registry should contain `input_sources.sources`. Each source may define `name`, `required`, `discovery_status`, and `source_path`. If `input_sources.mpas_jedi_build` exists, the tool also checks `build_root` and `variational_executable` in strict mode.

## Outputs and effects

The tool only reads files and prints audit messages. It does not create, copy, or link files. It returns `0` when the audit succeeds and `2` when strict checks fail or the registry structure is invalid.

## Examples

Minimum execution:

```bash
python tools/audit_input_sources.py
```

Strict audit:

```bash
python tools/audit_input_sources.py configs/experiments/3dvar_fgat/input_sources.yaml --strict
```

## Common errors

- `Registry must contain input_sources mapping`: the YAML file is not an input source registry.
- `input_sources.sources must be a list`: the `sources` section has the wrong type.
- `Required source file not found`: a required `source_path` does not point to an existing file in strict mode.

## Related tools

Use this before [`sync_input_sources.py`](03-sync-input-sources.md). It also complements [`check_mpas_jedi_build.py`](23-check-mpas-jedi-build.md).

[Back to tools index](../tools.md) | Previous: [bootstrap_data_layout.py](01-bootstrap-data-layout.md) | Next: [sync_input_sources.py](03-sync-input-sources.md)
