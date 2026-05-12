# MPAS-JEDI build discovery on JACI

This document describes how MONAN-JEDI-WORKFLOW discovers and validates the MPAS-JEDI build used by
the first 3DVar-FGAT experiment on JACI.

## Files

Manifest:

```text
configs/sites/jaci/mpas_jedi_build.example.yaml
```

Checker:

```text
tools/check_mpas_jedi_build.py
```

Wrapper:

```text
scripts/setup/check_mpas_jedi_build.sh
```

## Purpose

The workflow currently uses placeholders in `configs/sites/jaci/site.env`:

```bash
export MPAS_BUNDLE_BUILD="/path/to/mpas-bundle/build"
export MPAS_ATMOSPHERE_EXE="${MPAS_BUNDLE_BUILD}/bin/mpas_atmosphere"
export MPASJEDI_VARIATIONAL_EXE="${MPAS_BUNDLE_BUILD}/bin/mpasjedi_variational.x"
export MPASJEDI_HOFX_EXE="${MPAS_BUNDLE_BUILD}/bin/mpasjedi_hofx3d.x"
```

Before a real PBS run, these paths must point to a validated MPAS-JEDI build on JACI.

## Permissive check

During early setup:

```bash
bash scripts/setup/check_mpas_jedi_build.sh
```

This reports unresolved or missing paths as warnings.

## Strict check

After configuring the real build paths:

```bash
bash scripts/setup/check_mpas_jedi_build.sh --strict
```

Strict mode fails if required executables are missing or not executable.

## Required for first 3DVar-FGAT

The first 3DVar-FGAT case requires:

```text
mpasjedi_variational.x
```

The workflow also tracks:

```text
mpas_atmosphere
mpasjedi_hofx3d.x
```

`mpas_atmosphere` is needed for forecast cycling. `mpasjedi_hofx3d.x` is useful for HofX diagnostics.

## Suggested JACI procedure

1. Identify the validated `mpas-bundle` build directory.
2. Edit `configs/sites/jaci/site.env`:

```bash
export MPAS_BUNDLE_BUILD="/real/path/to/mpas-bundle/build"
export MPAS_ATMOSPHERE_EXE="${MPAS_BUNDLE_BUILD}/bin/mpas_atmosphere"
export MPASJEDI_VARIATIONAL_EXE="${MPAS_BUNDLE_BUILD}/bin/mpasjedi_variational.x"
export MPASJEDI_HOFX_EXE="${MPAS_BUNDLE_BUILD}/bin/mpasjedi_hofx3d.x"
```

3. Reload the environment:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

4. Run strict validation:

```bash
bash scripts/setup/check_mpas_jedi_build.sh --strict
```

5. Only proceed to real PBS submission after strict validation passes.

## Current limitation

This check validates paths and executable permissions only. It does not verify that the executable is
scientifically compatible with a specific JEDI YAML, MPAS mesh, covariance configuration or IODA
version.
