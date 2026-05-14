# FGAT window validation

This document describes the structural validation of the 3DVar-FGAT assimilation window for the first MONAN/JEDI experiment.

## Files

Validator:

```text
tools/validate_fgat_window.py
```

Wrapper:

```text
scripts/run/validate_3dvar_fgat_window.sh
```

Inputs:

```text
configs/experiments/3dvar_fgat/experiment.yaml
configs/experiments/3dvar_fgat/render_context.example.yaml
configs/experiments/3dvar_fgat/ioda_inventory.example.yaml
build/rendered/3dvar_fgat.yaml
```

## What is checked

The validator checks whether:

- `experiment.cycle` exists and follows `YYYYMMDDHH`;
- window begin/start is declared when available;
- window length or duration is parseable when available;
- date tokens in IODA paths match the experiment cycle;
- the render context visibly carries cycle-related temporal values;
- the rendered JEDI YAML contains recognizable temporal/window keys when available.

## Permissive mode

```bash
bash scripts/run/validate_3dvar_fgat_window.sh
```

Permissive mode reports missing or ambiguous temporal metadata as warnings.

## Strict mode

```bash
bash scripts/run/validate_3dvar_fgat_window.sh --strict
```

Strict mode should be enabled once the experiment YAML and rendered JEDI YAML have stable temporal fields.

## Recommended sequence

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env

bash scripts/run/render_3dvar_fgat.sh
bash scripts/run/validate_3dvar_fgat_window.sh
bash scripts/run/validate_3dvar_fgat_jedi_observers.sh
```

## Current boundary

This validation is structural only. It does not inspect actual observation timestamps inside IODA files, does not verify that every observation lies within the FGAT window, and does not validate MPAS background time metadata inside NetCDF files.

Those checks should be added after real files are staged and a validated MPAS-JEDI build is available.
