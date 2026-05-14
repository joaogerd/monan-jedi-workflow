# Rendered YAML temporal metadata

This document describes the explicit MONAN temporal metadata added to the rendered 3DVar-FGAT JEDI YAML.

## Purpose

The rendered JEDI YAML already contains the operational JEDI time window under:

```text
cost function.time window
```

This PR also adds a MONAN-side metadata block at the top of the rendered YAML:

```yaml
monan metadata:
  experiment: 3dvar_fgat
  analysis date: 2024-08-15T00:00:00Z
  cycle: 2024081500
  time window:
    begin: 2024-08-14T21:00:00Z
    length: PT6H
  mpas file date: 2024-08-15_00.00.00
```

The goal is traceability. This block makes it easier to validate, inspect and debug the rendered YAML
without relying only on deeply nested JEDI fields.

## Files changed

Template:

```text
configs/jedi/applications/3dvar_fgat.yaml
```

Validator:

```text
tools/validate_fgat_window.py
```

## Validation

Render the YAML:

```bash
bash scripts/run/render_3dvar_fgat.sh
```

Validate the FGAT window:

```bash
bash scripts/run/validate_3dvar_fgat_window.sh
```

Run strict validation once the rendered YAML consistently carries the temporal metadata:

```bash
bash scripts/run/validate_3dvar_fgat_window.sh --strict
```

## Current boundary

The metadata block is for MONAN workflow traceability. It should not be interpreted as a replacement
for JEDI's native configuration fields. The actual JEDI application still depends on the JEDI-recognized
configuration under `cost function` and related sections.
