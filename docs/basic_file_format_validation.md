# Basic file format validation

This document describes lightweight file-format validation for staged MONAN/JEDI 3DVar-FGAT inputs.

The validation runs after files have been staged under `${MONAN_DATA_ROOT}` and before attempting a
real JEDI-MPAS execution.

## Files

Validator:

```text
tools/validate_file_formats.py
```

Wrapper:

```text
scripts/setup/validate_3dvar_fgat_file_formats.sh
```

Default layout:

```text
configs/experiments/3dvar_fgat/data_layout.example.yaml
```

## What is checked

For each expected file declared in the data layout, the validator checks:

- whether the file exists;
- whether the path is a regular file;
- whether the file is non-empty;
- whether the extension is compatible with the declared `kind`;
- whether NetCDF files can be opened when `netCDF4` or `xarray` is available;
- whether HDF5 files can be opened when `h5py` is available.

## Permissive mode

```bash
bash scripts/setup/validate_3dvar_fgat_file_formats.sh
```

Permissive mode reports missing files as warnings. This is useful during structural workflow
development before real data are available.

## Strict mode

```bash
bash scripts/setup/validate_3dvar_fgat_file_formats.sh --strict
```

Strict mode fails when required files are missing, empty, have incompatible extensions or cannot be
opened by an available parser.

Use strict mode only after real files have been staged under `${MONAN_DATA_ROOT}`.

## Recommended JACI sequence

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env

bash scripts/setup/create_3dvar_fgat_external_tree.sh
bash scripts/setup/sync_3dvar_fgat_input_sources.sh \
  configs/experiments/3dvar_fgat/input_sources.jaci.yaml
bash scripts/setup/stage_3dvar_fgat_inputs.sh \
  configs/experiments/3dvar_fgat/staging.jaci.yaml
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/setup/validate_3dvar_fgat_file_formats.sh --strict
```

## Current boundary

This is not a scientific validation layer. It does not validate:

- IODA schema details;
- required UFO variables;
- MPAS mesh compatibility;
- valid analysis time or FGAT window coverage;
- covariance consistency;
- static/graph compatibility;
- compatibility between the files and the compiled MPAS-JEDI executable.

Those checks should be added in later validation layers after real files are available.
