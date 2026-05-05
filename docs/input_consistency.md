# Input consistency checks

This document describes consistency checks between the three input-control files for the first
MONAN/JEDI 3DVar-FGAT case.

## Files checked

Source registry:

```text
configs/experiments/3dvar_fgat/input_sources.example.yaml
```

Staging manifest:

```text
configs/experiments/3dvar_fgat/staging.example.yaml
```

Scientific checklist:

```text
configs/experiments/3dvar_fgat/scientific_input_checklist.yaml
```

## Checker

```text
tools/check_input_consistency.py
scripts/setup/check_3dvar_fgat_input_consistency.sh
```

## Usage

```bash
bash scripts/setup/check_3dvar_fgat_input_consistency.sh
```

With custom files:

```bash
bash scripts/setup/check_3dvar_fgat_input_consistency.sh \
  --sources configs/experiments/3dvar_fgat/input_sources.jaci.yaml \
  --staging configs/experiments/3dvar_fgat/staging.jaci.yaml \
  --checklist configs/experiments/3dvar_fgat/scientific_input_checklist.yaml
```

## What is checked

The checker validates that:

- every input in `input_sources` appears in `staging`;
- every input in `input_sources` appears in `scientific_input_checklist`;
- there are no extra entries in `staging` or `scientific_input_checklist`;
- `external_target` in `input_sources` matches `target` in `staging`;
- `staged_target` in `input_sources` matches `target` in `scientific_input_checklist`;
- `required` flags match across the three files;
- `kind` values match across the three files.

## Why this matters

The workflow now separates three concerns:

1. `input_sources`: where real files come from;
2. `staging`: how real files are linked or copied into `${MONAN_DATA_ROOT}`;
3. `scientific_input_checklist`: what must be validated before a real run.

This separation is useful, but it can create inconsistencies if one file is edited and the others are
not updated. The consistency checker prevents that drift.

## Current limitation

This checker validates configuration consistency only. It does not inspect scientific file contents,
NetCDF/HDF5 metadata, IODA schemas, covariance consistency or MPAS mesh compatibility.
