# External input root

This document describes the external input root used by the MONAN/JEDI 3DVar-FGAT staging layer.

The external input root is the location where real scientific input files are collected before they
are linked or copied into `${MONAN_DATA_ROOT}`.

## Variable

```bash
export MONAN_EXTERNAL_DATA_ROOT=/path/to/external/inputs
```

On JACI, the example default is:

```bash
export MONAN_EXTERNAL_DATA_ROOT="${MONAN_JACI_WORKSPACE}/external-inputs/3dvar_fgat"
```

## Checker

```text
scripts/setup/check_external_input_root.sh
```

## Permissive mode

During early setup, the directory may not exist yet:

```bash
bash scripts/setup/check_external_input_root.sh --allow-missing
```

## Strict mode

After choosing a real input location:

```bash
bash scripts/setup/check_external_input_root.sh
```

Strict mode fails if `MONAN_EXTERNAL_DATA_ROOT` is missing, unresolved or not a directory.

## Relation to input staging

The staging manifest uses paths such as:

```text
${MONAN_EXTERNAL_DATA_ROOT}/background/2024081500/mpasout.2024-08-15_00.00.00.nc
${MONAN_EXTERNAL_DATA_ROOT}/observations/ioda/2024081500/aircraft_obs_2024081500.h5
${MONAN_EXTERNAL_DATA_ROOT}/covariance/mpas.stddev.nc
```

Once the external input root is populated, run:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
bash scripts/setup/stage_3dvar_fgat_inputs.sh
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
```

## Current limitation

This check validates the root directory and reports source parent directories from the staging
manifest. It does not inspect file contents.
