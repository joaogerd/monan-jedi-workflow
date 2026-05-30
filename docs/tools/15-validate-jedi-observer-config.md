# 15. validate_jedi_observer_config.py

[Back to tools index](../tools.md) | Previous: [render_observers.py](14-render-observers.md) | Next: [check_placeholders.py](16-check-placeholders.md)

## Purpose

`validate_jedi_observer_config.py` checks whether the rendered JEDI YAML contains the observers expected by the observer manifest and IODA inventory.

## Context of use

Run this after rendering the final JEDI YAML. It helps identify missing observer blocks, unexpected observers, or observers without an `obsdatain.engine.obsfile` field.

## Location

```text
tools/validate_jedi_observer_config.py
```

## Prerequisites

Python 3, PyYAML, a rendered JEDI YAML file, an observer manifest, and an IODA inventory.

## How to run

```bash
python tools/validate_jedi_observer_config.py [--jedi-yaml FILE] [--observer-manifest FILE] [--ioda-inventory FILE] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--jedi-yaml` | Rendered JEDI application YAML. |
| `--observer-manifest` | Observer manifest. |
| `--ioda-inventory` | IODA inventory. |
| `--strict` | Fails if expected observers are missing or unexpected observers are present. |

## Inputs and outputs

The tool recursively scans the rendered YAML for observer blocks with `obs space.name`. It prints expected observers, rendered observers, and each observer obsfile.

## Examples

```bash
python tools/validate_jedi_observer_config.py
```

```bash
python tools/validate_jedi_observer_config.py --jedi-yaml build/rendered/3dvar_fgat.yaml --strict
```

## Common errors

- Rendered JEDI YAML not found.
- Expected observer missing from rendered YAML.
- Rendered observer not declared in manifest or inventory.
- Observer has no `obsdatain.engine.obsfile`.

## Related tools

Use after [`render_observers.py`](14-render-observers.md) and with [`check_ioda_inventory.py`](10-check-ioda-inventory.md).

[Back to tools index](../tools.md) | Previous: [render_observers.py](14-render-observers.md) | Next: [check_placeholders.py](16-check-placeholders.md)
