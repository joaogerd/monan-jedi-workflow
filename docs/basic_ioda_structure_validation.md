# Basic IODA structure validation

This document describes lightweight IODA/HDF5 structure validation for the first MONAN/JEDI
3DVar-FGAT experiment.

This validation is intended to run after IODA files have been staged under `${MONAN_DATA_ROOT}` and
before attempting a real JEDI-MPAS execution.

## Files

Validator:

```text
tools/validate_ioda_structure.py
```

Wrapper:

```text
scripts/setup/validate_3dvar_fgat_ioda_structure.sh
```

Inputs:

```text
configs/experiments/3dvar_fgat/ioda_inventory.example.yaml
configs/experiments/3dvar_fgat/observers.yaml
configs/jedi/obs_plugs/variational/*.yaml
```

## What is checked

For each IODA file declared in the inventory, the validator checks:

- file exists;
- file is a regular file;
- file is non-empty;
- file can be opened with `h5py`, if available;
- root groups are listed;
- common IODA groups are reported:
  - `MetaData`
  - `ObsValue`
  - `ObsError`
  - `PreQC`
- expected simulated variables from the observer plug are compared with variables found under
  `ObsValue`, when possible.

## Permissive mode

```bash
bash scripts/setup/validate_3dvar_fgat_ioda_structure.sh
```

Permissive mode reports missing or incomplete files as warnings. This is useful while real IODA files
are not yet staged.

## Strict mode

```bash
bash scripts/setup/validate_3dvar_fgat_ioda_structure.sh --strict
```

Strict mode should be used only after real IODA files have been staged.

## Recommended sequence

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env

bash scripts/setup/stage_3dvar_fgat_inputs.sh \
  configs/experiments/3dvar_fgat/staging.jaci.yaml

bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/setup/validate_3dvar_fgat_file_formats.sh --strict
bash scripts/setup/validate_3dvar_fgat_ioda_structure.sh --strict
```

## Current boundary

This is not a complete IODA/UFO scientific validation layer. It does not guarantee:

- correct IODA schema for a specific UFO operator;
- correct units;
- correct coordinates;
- correct FGAT time-window coverage;
- correct bias correction setup;
- correct observation errors;
- correct quality-control flags;
- scientific compatibility with the selected MPAS-JEDI executable.

Those checks should be added after real IODA files are available on JACI.
