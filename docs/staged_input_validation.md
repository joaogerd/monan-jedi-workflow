# Staged input validation

This document describes the lightweight staged-input validation layer for the MONAN/JEDI
3DVar-FGAT workflow.

The goal is to check whether expected scientific input files have been staged under
`${MONAN_DATA_ROOT}` before attempting strict runtime preparation or PBS execution.

## Files

Validator:

```text
tools/validate_staged_inputs.py
```

Wrapper:

```text
scripts/setup/validate_3dvar_fgat_staged_inputs.sh
```

Layout source:

```text
configs/experiments/3dvar_fgat/data_layout.example.yaml
```

## Permissive mode

During early setup, missing files should be warnings:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh --allow-missing
```

This mode is used by the smoke test.

## Strict mode

After staging input files, run:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
```

Strict mode fails when expected files are missing, empty or not regular files.

## What is checked

The validator checks:

- expected file paths from `data_layout.example.yaml`;
- existence, unless `--allow-missing` is used;
- regular-file status;
- non-zero file size;
- broad file kind based on filename extension.

## What is not checked yet

This validator does not inspect NetCDF/HDF5 internals. It does not check:

- NetCDF dimensions or variables;
- IODA group structure;
- MPAS mesh compatibility;
- graph partition compatibility;
- covariance compatibility;
- JEDI schema or UFO semantics.

Those checks should be added later using dedicated NetCDF/HDF5-aware tools once real JACI files are
available.
