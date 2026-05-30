# 13. check_observer_metadata.py

[Back to tools index](../tools.md) | Previous: [check_observer_manifest.py](12-check-observer-manifest.md) | Next: [render_observers.py](14-render-observers.md)

## Purpose

`check_observer_metadata.py` checks whether all observers declared in the experiment manifest have corresponding metadata in the observer plug registry.

## Context of use

Run this before rendering observers. It verifies metadata coverage and helps keep observer templates, categories, validation status, and notes documented.

## Location

```text
tools/check_observer_metadata.py
```

## Prerequisites

Python 3, PyYAML, an observer manifest, and observer metadata with top-level `observer_plugs`.

## How to run

```bash
python tools/check_observer_metadata.py [--manifest FILE] [--metadata FILE]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `--manifest` | Observer manifest. |
| `--metadata` | Observer plug metadata registry. |

## Inputs and outputs

The tool checks that metadata exists for each manifest observer and contains required fields such as `template`, `status`, `category`, `expected_ioda_group`, `requires_bias_correction`, `validated_on_jaci`, and `notes`.

## Examples

```bash
python tools/check_observer_metadata.py
```

```bash
python tools/check_observer_metadata.py --manifest configs/experiments/3dvar_fgat/observers.yaml --metadata configs/jedi/obs_plugs/variational/metadata.yaml
```

## Common errors

- Manifest lacks an `observers` list.
- Metadata lacks `observer_plugs`.
- Metadata missing for an observer.
- Metadata missing required keys.
- Template mismatch between manifest and metadata.

## Related tools

Use after [`check_observer_manifest.py`](12-check-observer-manifest.md) and before [`render_observers.py`](14-render-observers.md).

[Back to tools index](../tools.md) | Previous: [check_observer_manifest.py](12-check-observer-manifest.md) | Next: [render_observers.py](14-render-observers.md)
