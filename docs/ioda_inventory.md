# IODA inventory validation

This document describes the initial IODA inventory layer for MONAN-JEDI-WORKFLOW.

The purpose is to make expected observation files explicit before running JEDI-MPAS. This helps
connect the observer manifest, observer metadata and runtime file preparation.

## Files

Inventory example:

```text
configs/experiments/3dvar_fgat/ioda_inventory.example.yaml
```

Checker:

```text
tools/check_ioda_inventory.py
```

## Inventory structure

```yaml
ioda_inventory:
  cycle: "2024081500"
  root: "${MONAN_DATA_ROOT}/observations/ioda/2024081500"
  feedback_root: "${MONAN_SCRATCH}/jaci_3dvar_fgat_smoke/feedback"
  files:
    - observer: aircraft
      required: true
      path: "${MONAN_DATA_ROOT}/observations/ioda/2024081500/aircraft_obs_2024081500.h5"
      feedback_path: "${MONAN_SCRATCH}/jaci_3dvar_fgat_smoke/feedback/aircraft_oman_2024081500.h5"
      expected_group: aircraft
      status: structural_placeholder
```

## Local structural check

```bash
python3 tools/check_ioda_inventory.py \
  --inventory configs/experiments/3dvar_fgat/ioda_inventory.example.yaml \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml
```

This mode accepts unresolved variables such as `${MONAN_DATA_ROOT}` and does not require files to
exist.

## Strict file check on JACI

After configuring `configs/sites/jaci/site.env` and placing real IODA files under the configured
data root, run:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env

python3 tools/check_ioda_inventory.py \
  --inventory configs/experiments/3dvar_fgat/ioda_inventory.example.yaml \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml \
  --strict-files
```

## What is checked

The checker validates that:

- each IODA inventory entry refers to an enabled observer;
- each enabled observer appears in the inventory;
- each inventory entry has metadata;
- `expected_group` matches the metadata registry;
- paths are present;
- required files exist when `--strict-files` is used.

## What is not checked yet

This checker does not inspect HDF5/IODA contents. It does not validate:

- IODA groups and variables;
- observation values;
- metadata fields;
- variable naming compatibility with UFO;
- timestamps inside the assimilation window;
- missing-value conventions;
- channel metadata for radiances.

Those checks should be added later after real IODA files are available on JACI.
