# 18. validate_experiment.py

[Back to tools index](../tools.md) | Previous: [render_template.py](17-render-template.md) | Next: [validate_fgat_window.py](19-validate-fgat-window.md)

## Purpose

`validate_experiment.py` performs structural validation of the experiment directory and rendered products.

## Context of use

Run this after rendering the workflow files. It checks that expected configuration files and rendered outputs exist and contain important text markers.

## Location

```text
tools/validate_experiment.py
```

## Prerequisites

Python 3, PyYAML, experiment configuration files, and rendered products under `build/rendered` or another selected directory.

## How to run

```bash
python tools/validate_experiment.py [--experiment-dir DIR] [--rendered-dir DIR]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--experiment-dir` | Experiment configuration directory. Defaults to `configs/experiments/3dvar_fgat`. |
| `--rendered-dir` | Rendered output directory. Defaults to `build/rendered`. |

## Inputs and outputs

The tool checks required top-level YAML keys and rendered files such as `3dvar_fgat.yaml`, `observers.yaml`, `mpasjedi_variational.command`, and `3dvar_fgat.pbs`. It prints `[INFO]` on successful checks and returns `2` on validation failure.

## Examples

```bash
python tools/validate_experiment.py
```

```bash
python tools/validate_experiment.py --experiment-dir configs/experiments/3dvar_fgat --rendered-dir build/rendered
```

## Common errors

- Missing YAML file.
- Missing top-level key.
- Missing rendered file.
- Expected text not found in rendered product.

## Related tools

Use after [`render_template.py`](17-render-template.md), [`render_observers.py`](14-render-observers.md), and before [`run_variational.py`](25-run-variational.md).

[Back to tools index](../tools.md) | Previous: [render_template.py](17-render-template.md) | Next: [validate_fgat_window.py](19-validate-fgat-window.md)
