# 14. render_observers.py

[Back to tools index](../tools.md) | Previous: [check_observer_metadata.py](13-check-observer-metadata.md) | Next: [validate_jedi_observer_config.py](15-validate-jedi-observer-config.md)

## Purpose

`render_observers.py` renders enabled JEDI observer plug templates and concatenates them into one YAML fragment.

## Context of use

Run this after observer manifest and metadata checks. The generated fragment is used by the rendered JEDI application YAML under the observations section.

## Location

```text
tools/render_observers.py
```

## Prerequisites

Python 3, PyYAML, an observer manifest, a rendering context, and template files referenced by enabled observers.

## How to run

```bash
python tools/render_observers.py manifest --context context.yaml --output output.yaml [--allow-env] [--allow-unresolved]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `manifest` | Observer manifest YAML. |
| `--context` | Required YAML rendering context. |
| `--output` | Required output observers YAML fragment. |
| `--allow-env` | Allows `{{name}}` placeholders to be resolved from environment variables. |
| `--allow-unresolved` | Preserves unresolved placeholders instead of failing. |

## Inputs and outputs

The tool reads enabled entries from the manifest, renders each referenced template with the shared context, and writes a concatenated YAML fragment.

## Examples

```bash
python tools/render_observers.py configs/experiments/3dvar_fgat/observers.yaml --context configs/experiments/3dvar_fgat/render_context.yaml --output build/rendered/observers.yaml
```

```bash
python tools/render_observers.py observers.yaml --context context.yaml --output observers.rendered.yaml --allow-unresolved
```

## Common errors

- Observer manifest does not contain an `observers` list.
- Enabled observer template is missing.
- Unresolved placeholders remain and `--allow-unresolved` was not used.

## Related tools

Uses rendering behavior from [`render_template.py`](17-render-template.md). Validate the result with [`validate_jedi_observer_config.py`](15-validate-jedi-observer-config.md).

[Back to tools index](../tools.md) | Previous: [check_observer_metadata.py](13-check-observer-metadata.md) | Next: [validate_jedi_observer_config.py](15-validate-jedi-observer-config.md)
