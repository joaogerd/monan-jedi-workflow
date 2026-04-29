# Input staging

This document describes how to stage external scientific input files into the canonical
`${MONAN_DATA_ROOT}` layout used by MONAN-JEDI-WORKFLOW.

The staging layer does not create scientific data. It only links or copies real files from an
external source directory into the workflow data tree.

## Files

Manifest:

```text
configs/experiments/3dvar_fgat/staging.example.yaml
```

Tool:

```text
tools/stage_inputs.py
```

Wrapper:

```text
scripts/setup/stage_3dvar_fgat_inputs.sh
```

## Required environment variable

The example manifest uses:

```text
${MONAN_EXTERNAL_DATA_ROOT}
```

This variable should point to the location where the real experiment input files are staged before
being linked or copied into `${MONAN_DATA_ROOT}`.

Example:

```bash
export MONAN_EXTERNAL_DATA_ROOT=/p/projetos/monan_das/shared/inputs/3dvar_fgat
```

## Dry-run

Always inspect actions first:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
```

## Link files

The default action in the example manifest is `link`:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh
```

To force links explicitly:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --link
```

## Copy files

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --copy
```

## Replace existing targets

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --force
```

Use this carefully. It removes existing targets before staging new ones.

## Validation after staging

After staging files, run:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
python3 tools/check_ioda_inventory.py \
  --inventory configs/experiments/3dvar_fgat/ioda_inventory.example.yaml \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml \
  --strict-files
```

## Current limitations

The staging layer does not validate scientific content. It does not inspect NetCDF/HDF5 internals,
IODA groups, MPAS mesh compatibility, graph partition compatibility or covariance consistency.
