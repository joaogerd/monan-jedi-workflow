# 17. render_template.py

[Back to tools index](../tools.md) | Previous: [check_placeholders.py](16-check-placeholders.md) | Next: [validate_experiment.py](18-validate-experiment.md)

## Purpose

`render_template.py` renders text templates using values from a YAML context file and, when allowed, environment variables.

## Context of use

Use this to produce rendered YAML, shell, PBS, or command files from templates. It is the generic rendering layer used by the workflow.

## Location

```text
tools/render_template.py
```

## Prerequisites

Python 3 and PyYAML. A template file is required. A YAML context file is optional but normally used.

## How to run

```bash
python tools/render_template.py template [-c context.yaml] [-o output] [--allow-env] [--allow-unresolved]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `template` | Input template file. |
| `-c`, `--context` | YAML context file with replacement values. |
| `-o`, `--output` | Output file. If omitted, output is printed to stdout. |
| `--allow-env` | Allows `{{name}}` placeholders to use environment variables. |
| `--allow-unresolved` | Writes output even when placeholders remain unresolved. |

## Inputs and outputs

The tool supports `{{key}}`, nested keys such as `{{experiment.name}}`, and `${NAME}` placeholders. It writes rendered text to a file or stdout. Unresolved placeholders cause exit code `2` unless allowed.

## Examples

```bash
python tools/render_template.py templates/3dvar_fgat.yaml.template -c context.yaml
```

```bash
python tools/render_template.py input.template -c context.yaml -o build/rendered/input.yaml --allow-unresolved
```

## Common errors

- Context file missing.
- Context YAML is not a mapping.
- Unresolved placeholders remain.

## Related tools

Used by [`render_observers.py`](14-render-observers.md). Inspect unresolved values with [`check_placeholders.py`](16-check-placeholders.md).

[Back to tools index](../tools.md) | Previous: [check_placeholders.py](16-check-placeholders.md) | Next: [validate_experiment.py](18-validate-experiment.md)
