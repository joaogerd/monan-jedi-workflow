# JACI real input preparation

This document describes the JACI-specific templates for preparing real scientific inputs for the
first MONAN/JEDI 3DVar-FGAT experiment.

## Files

JACI source registry template:

```text
configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml
```

JACI staging template:

```text
configs/experiments/3dvar_fgat/staging.jaci.example.yaml
```

External tree helper:

```text
scripts/setup/create_3dvar_fgat_external_tree.sh
```

## Create the external input tree

Load the JACI environment first:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

Inspect the planned directories:

```bash
bash scripts/setup/create_3dvar_fgat_external_tree.sh --dry-run
```

Create them:

```bash
bash scripts/setup/create_3dvar_fgat_external_tree.sh
```

The expected tree is:

```text
${MONAN_EXTERNAL_DATA_ROOT}/
├── background/2024081500/
├── observations/ioda/2024081500/
├── covariance/
├── graph/
└── static/
```

## Prepare source registry

Copy the JACI example:

```bash
cp configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml \
   configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

Fill `source_path` values with the real files available on JACI.

Then audit:

```bash
bash scripts/setup/audit_3dvar_fgat_input_sources.sh \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

Use strict mode after all required sources are filled:

```bash
bash scripts/setup/audit_3dvar_fgat_input_sources.sh --strict \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

## Prepare staging manifest

Copy the JACI staging example if customization is needed:

```bash
cp configs/experiments/3dvar_fgat/staging.jaci.example.yaml \
   configs/experiments/3dvar_fgat/staging.jaci.yaml
```

Check consistency:

```bash
bash scripts/setup/check_3dvar_fgat_input_consistency.sh \
  --sources configs/experiments/3dvar_fgat/input_sources.jaci.yaml \
  --staging configs/experiments/3dvar_fgat/staging.jaci.yaml \
  --checklist configs/experiments/3dvar_fgat/scientific_input_checklist.yaml
```

## Stage files

Dry-run:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run \
  configs/experiments/3dvar_fgat/staging.jaci.yaml
```

Stage using links:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh \
  configs/experiments/3dvar_fgat/staging.jaci.yaml
```

Validate staged files:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
```

## Required files for the first case

```text
background/2024081500/mpasout.2024-08-15_00.00.00.nc
observations/ioda/2024081500/aircraft_obs_2024081500.h5
observations/ioda/2024081500/sondes_obs_2024081500.h5
observations/ioda/2024081500/sfc_obs_2024081500.h5
covariance/mpas.stddev.nc
```

Optional or configuration-dependent files:

```text
graph/graph.info.part.0128
static/x1.static.nc
```

## Current boundary

These templates organize paths and staging. They do not generate scientific input data and do not
validate NetCDF/HDF5 internals, IODA schemas, covariance consistency or MPAS mesh compatibility.
