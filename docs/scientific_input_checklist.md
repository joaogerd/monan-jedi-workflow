# Scientific input checklist

This document describes the scientific input checklist for the first MONAN/JEDI 3DVar-FGAT
experiment.

The checklist is not a data generator. It documents what must be provided before attempting a real
JEDI-MPAS run on JACI.

## Files

Checklist:

```text
configs/experiments/3dvar_fgat/scientific_input_checklist.yaml
```

Auditor:

```text
tools/audit_scientific_inputs.py
```

Wrapper:

```text
scripts/setup/audit_3dvar_fgat_scientific_inputs.sh
```

## Audit

```bash
bash scripts/setup/audit_3dvar_fgat_scientific_inputs.sh
```

This reports each expected input, its current status and whether the corresponding target file
exists under `${MONAN_DATA_ROOT}`.

## Strict audit

```bash
bash scripts/setup/audit_3dvar_fgat_scientific_inputs.sh --strict
```

Strict mode fails if required inputs are not marked as either:

- `validated_basic`
- `validated_scientific`

Use strict mode only after real files have been staged and basic/scientific validation has been
performed.

## Current required inputs

The first 3DVar-FGAT experiment expects:

- MPAS background state:
  - `background/2024081500/mpasout.2024-08-15_00.00.00.nc`

- IODA observations:
  - `observations/ioda/2024081500/aircraft_obs_2024081500.h5`
  - `observations/ioda/2024081500/sondes_obs_2024081500.h5`
  - `observations/ioda/2024081500/sfc_obs_2024081500.h5`

- Covariance resource:
  - `covariance/mpas.stddev.nc`

Optional/currently contextual inputs:

- graph partition file:
  - `graph/graph.info.part.0128`

- static file:
  - `static/x1.static.nc`

## Status values

The checklist uses descriptive statuses:

- `pending_source`
- `staged_unvalidated`
- `validated_basic`
- `validated_scientific`

## Important limitation

This checklist documents readiness. It does not inspect NetCDF/HDF5 internals, validate IODA
schemas, validate MPAS mesh compatibility or guarantee scientific correctness.

Those deeper checks should be implemented after the first real input files are identified and staged
on JACI.
