# SABER/BUMP input validation

This document describes the lightweight validation of SABER/BUMP input paths for the first MONAN/JEDI 3DVar-FGAT experiment.

## Files

```text
tools/validate_saber_inputs.py
scripts/setup/validate_3dvar_fgat_saber_inputs.sh
```

## Inputs checked

The validator reads the JEDI render context and inspects these entries:

```text
jedi.bump_cov_stddev_file
jedi.bump_cov_dir
jedi.bump_cov_vbal_dir
```

These correspond to:

```text
${MONAN_DATA_ROOT}/covariance/mpas.stddev.nc
${MONAN_DATA_ROOT}/covariance/NICAS
${MONAN_DATA_ROOT}/covariance/VBAL
```

## Permissive mode

```bash
bash scripts/setup/validate_3dvar_fgat_saber_inputs.sh
```

Permissive mode reports missing paths as warnings. This is appropriate while the real covariance resources have not yet been staged.

## Strict mode

```bash
bash scripts/setup/validate_3dvar_fgat_saber_inputs.sh --strict
```

Strict mode should be used after real SABER/BUMP files have been staged.

## Boundary

This is a path-level validation layer. It does not yet validate full SABER/BUMP scientific compatibility, covariance variable content, MPAS mesh compatibility or consistency with the selected MPAS-JEDI executable.
