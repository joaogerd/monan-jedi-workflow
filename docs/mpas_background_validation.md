# MPAS background validation

This document describes the lightweight validation of the staged MPAS background file for the first MONAN/JEDI 3DVar-FGAT experiment.

## Files

```text
tools/validate_mpas_background.py
scripts/setup/validate_3dvar_fgat_mpas_background.sh
```

## Default background file

```text
${MONAN_DATA_ROOT}/background/2024081500/mpasout.2024-08-15_00.00.00.nc
```

## Checks

The validator checks whether the background file exists, is a regular file, is not empty, has a NetCDF-like extension, and can be opened with `netCDF4` or `xarray` when one of them is available.

When the file can be opened, the validator reports the number of dimensions and variables, checks whether the expected JEDI state variables are present, and reports whether obvious temporal global attributes are available.

## Permissive mode

```bash
bash scripts/setup/validate_3dvar_fgat_mpas_background.sh
```

Permissive mode reports missing or incomplete files as warnings.

## Strict mode

```bash
bash scripts/setup/validate_3dvar_fgat_mpas_background.sh --strict
```

Strict mode should be used only after the real background file has been staged.

## Suggested JACI sequence

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
bash scripts/setup/stage_3dvar_fgat_inputs.sh configs/experiments/3dvar_fgat/staging.jaci.yaml
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/setup/validate_3dvar_fgat_file_formats.sh --strict
bash scripts/setup/validate_3dvar_fgat_mpas_background.sh --strict
```

## Boundary

This is not a scientific validation of the background state. It only provides basic file and metadata checks before attempting a real JEDI-MPAS run.
