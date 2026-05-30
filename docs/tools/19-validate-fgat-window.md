# 19. validate_fgat_window.py

[Back to tools index](../tools.md) | Previous: [validate_experiment.py](18-validate-experiment.md) | Next: [validate_mpas_background.py](20-validate-mpas-background.md)

## Purpose

`validate_fgat_window.py` checks whether 3DVar-FGAT temporal metadata is consistent across the experiment file, render context, IODA inventory, and rendered JEDI YAML.

## Context of use

Run this after rendering the workflow files or before submitting a JEDI job. It helps identify mismatched cycles, missing window length, and inconsistent date tokens.

## Location

```text
tools/validate_fgat_window.py
```

## Prerequisites

Python 3, PyYAML, and the experiment YAML files used by the 3DVar-FGAT case.

## How to run

```bash
python tools/validate_fgat_window.py [--experiment FILE] [--render-context FILE] [--jedi-yaml FILE] [--ioda-inventory FILE] [--strict]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--experiment` | Experiment YAML. |
| `--render-context` | Render context YAML. |
| `--jedi-yaml` | Rendered JEDI YAML. |
| `--ioda-inventory` | IODA inventory YAML. |
| `--strict` | Turns warnings about missing or ambiguous metadata into failures. |

## Inputs and outputs

The tool prints the cycle, declared and inferred window information, IODA date-token checks, and temporal keys found in the rendered JEDI YAML. It returns `2` on strict failures.

## Examples

```bash
python tools/validate_fgat_window.py
```

```bash
python tools/validate_fgat_window.py --jedi-yaml build/rendered/3dvar_fgat.yaml --strict
```

## Common errors

- Missing experiment cycle.
- Unparseable cycle or window length.
- IODA path token does not match the experiment cycle.
- Rendered JEDI YAML is missing temporal/window keys.

## Related tools

Use with [`validate_experiment.py`](18-validate-experiment.md) and [`validate_jedi_observer_config.py`](15-validate-jedi-observer-config.md).

[Back to tools index](../tools.md) | Previous: [validate_experiment.py](18-validate-experiment.md) | Next: [validate_mpas_background.py](20-validate-mpas-background.md)
