# 12. check_observer_manifest.py

[Back to tools index](../tools.md) | Previous: [validate_ioda_structure.py](11-validate-ioda-structure.md) | Next: [check_observer_metadata.py](13-check-observer-metadata.md)

## Purpose

`check_observer_manifest.py` validates the structure of the observer manifest used by the experiment.

## Context of use

Run this before rendering observer templates. It confirms that each observer entry has a valid name, template path, and enabled flag.

## Location

```text
tools/check_observer_manifest.py
```

## Prerequisites

Python 3, PyYAML, and a manifest containing a top-level `observers` list.

## How to run

```bash
python tools/check_observer_manifest.py [manifest]
```

## Parameters

| Parameter | Meaning |
|---|---|
| `manifest` | Optional observer manifest. Defaults to `configs/experiments/3dvar_fgat/observers.yaml`. |

## Inputs and outputs

The tool reads the observer manifest and each referenced template. It checks duplicate names, empty names, invalid `enabled` flags, missing templates, and whether the observer name appears in the template text.

## Examples

```bash
python tools/check_observer_manifest.py
```

```bash
python tools/check_observer_manifest.py configs/experiments/3dvar_fgat/observers.yaml
```

## Common errors

- Manifest is missing or lacks an `observers` list.
- Observer entry is not a mapping.
- Duplicate observer name.
- Invalid or missing template path.
- Observer name not found in the template.

## Related tools

Use before [`check_observer_metadata.py`](13-check-observer-metadata.md) and [`render_observers.py`](14-render-observers.md).

[Back to tools index](../tools.md) | Previous: [validate_ioda_structure.py](11-validate-ioda-structure.md) | Next: [check_observer_metadata.py](13-check-observer-metadata.md)
