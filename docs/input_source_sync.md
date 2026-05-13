# Input source synchronization

This document describes how to synchronize real input files declared in an `input_sources` registry
into `${MONAN_EXTERNAL_DATA_ROOT}`.

The synchronization layer sits before the existing staging layer:

```text
real source files -> MONAN_EXTERNAL_DATA_ROOT -> MONAN_DATA_ROOT
```

## Files

Tool:

```text
tools/sync_input_sources.py
```

Wrapper:

```text
scripts/setup/sync_3dvar_fgat_input_sources.sh
```

JACI source registry template:

```text
configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml
```

## Conservative behavior

This first version is intentionally conservative:

- default mode creates symbolic links;
- `--copy` copies files instead of linking;
- existing targets are never replaced;
- missing required sources fail outside dry-run mode;
- empty `source_path` values are warnings in dry-run mode and errors in real mode.

## Dry-run

```bash
bash scripts/setup/sync_3dvar_fgat_input_sources.sh --dry-run \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

## Link files into MONAN_EXTERNAL_DATA_ROOT

```bash
bash scripts/setup/sync_3dvar_fgat_input_sources.sh \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

## Copy files instead of linking

```bash
bash scripts/setup/sync_3dvar_fgat_input_sources.sh --copy \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

## Recommended JACI workflow

1. Load the JACI environment:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

2. Create the external input tree:

```bash
bash scripts/setup/create_3dvar_fgat_external_tree.sh
```

3. Prepare a local registry:

```bash
cp configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml \
   configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

4. Fill `source_path` values with real files on JACI.

5. Audit the registry:

```bash
bash scripts/setup/audit_3dvar_fgat_input_sources.sh \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

6. Dry-run synchronization:

```bash
bash scripts/setup/sync_3dvar_fgat_input_sources.sh --dry-run \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

7. Synchronize into `${MONAN_EXTERNAL_DATA_ROOT}`:

```bash
bash scripts/setup/sync_3dvar_fgat_input_sources.sh \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

8. Stage from `${MONAN_EXTERNAL_DATA_ROOT}` into `${MONAN_DATA_ROOT}`:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh \
  configs/experiments/3dvar_fgat/staging.jaci.yaml
```

9. Validate staged inputs:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
```

## Current limitation

This synchronization step only moves or links files. It does not validate NetCDF/HDF5 internals,
IODA schema compatibility, MPAS mesh consistency, covariance compatibility or scientific readiness.
