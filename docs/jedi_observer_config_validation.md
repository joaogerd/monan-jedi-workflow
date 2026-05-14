# Rendered JEDI observer configuration validation

This document describes the structural validation of the rendered JEDI YAML against the observer
manifest and IODA inventory for the first MONAN/JEDI 3DVar-FGAT experiment.

## Files

Validator:

```text
tools/validate_jedi_observer_config.py
```

Wrapper:

```text
scripts/run/validate_3dvar_fgat_jedi_observers.sh
```

Inputs:

```text
build/rendered/3dvar_fgat.yaml
configs/experiments/3dvar_fgat/observers.yaml
configs/experiments/3dvar_fgat/ioda_inventory.example.yaml
```

## What is checked

The validator checks whether:

- the rendered JEDI YAML exists;
- expected observers from the observer manifest appear in the rendered YAML;
- expected observers from the IODA inventory appear in the rendered YAML;
- rendered observers are declared in the manifest/inventory;
- each rendered observer has `obs space.name`;
- each rendered observer has an `obsdatain.engine.obsfile` entry.

## Permissive mode

```bash
bash scripts/run/validate_3dvar_fgat_jedi_observers.sh
```

Permissive mode reports missing/extra observers as warnings.

## Strict mode

```bash
bash scripts/run/validate_3dvar_fgat_jedi_observers.sh --strict
```

Strict mode fails if expected observers are missing, undeclared observers are present, or observer
input files are not declared in the rendered YAML.

## Recommended sequence

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env

bash scripts/run/render_3dvar_fgat.sh
bash scripts/run/validate_3dvar_fgat_jedi_observers.sh --strict
```

## Current boundary

This is a structural validation layer. It does not verify whether the rendered observer configuration
is scientifically valid for UFO/JEDI execution. It also does not validate:

- full UFO operator compatibility;
- variable units;
- bias correction configuration;
- observation error models;
- QC filters;
- localization/covariance consistency;
- FGAT time-window coverage.

Those checks require real IODA files and a validated MPAS-JEDI build.
