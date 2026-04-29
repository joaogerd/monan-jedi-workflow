# Experiment structural validation

This document describes the structural validation command for the MONAN/JEDI 3DVar-FGAT workflow.

The validator is a pre-flight check. It verifies that the experiment configuration and rendered
artifacts are internally consistent enough to inspect before running on JACI.

It does not validate scientific correctness.

## Files

Validator:

```text
tools/validate_experiment.py
```

Wrapper:

```text
scripts/run/validate_3dvar_fgat_experiment.sh
```

## Run

```bash
bash scripts/run/validate_3dvar_fgat_experiment.sh
```

This command runs the current structural chain:

1. render observers;
2. render the 3DVar-FGAT JEDI YAML;
3. prepare runtime in dry-run mode;
4. build the variational command in dry-run mode;
5. render the PBS job;
6. validate expected configuration files and rendered outputs.

## What is checked

The validator checks that these experiment files exist and have expected top-level sections:

- `experiment.yaml` -> `experiment`;
- `observers.yaml` -> `observers`;
- `runtime_manifest.example.yaml` -> `runtime`;
- `run_command.example.yaml` -> `variational_run`;
- `pbs_job.example.yaml` -> `pbs`.

It also checks that rendered outputs contain key structural content:

- `build/rendered/3dvar_fgat.yaml`;
- `build/rendered/observers.yaml`;
- `build/rendered/mpasjedi_variational.command`;
- `build/rendered/3dvar_fgat.pbs`.

## Current limitations

The validator does not yet check:

- JEDI YAML schema;
- UFO observer validity;
- IODA file schema;
- NetCDF/HDF5 file contents;
- graph partition compatibility;
- MPAS namelist/stream correctness;
- PBS account/queue validity;
- scientific consistency of variables and covariance resources.

These checks should be added gradually as the workflow moves from structural smoke tests to real
JACI execution.
