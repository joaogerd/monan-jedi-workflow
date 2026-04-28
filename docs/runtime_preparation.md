# Runtime preparation

This document describes the first MONAN-JEDI-WORKFLOW runtime preparation layer.

The goal is to prepare the directory tree and required input file links before launching
`mpasjedi_variational.x`.

This is a replacement candidate for part of the upstream `PrepJEDI.csh` behavior, but it is not yet
a full replacement.

## Why this layer exists

Before a JEDI-MPAS variational task runs, the workflow must ensure that the runtime directory has:

- rendered JEDI YAML files;
- background MPAS states;
- observation files in IODA format;
- feedback output directories;
- covariance resources;
- graph partition files;
- static/invariant files;
- logs and analysis output directories.

The upstream MPAS-Workflow handles much of this inside C-shell task scripts. In MONAN-JEDI-WORKFLOW,
we want this to be explicit, auditable and testable before submitting HPC jobs.

## Files

Manifest:

```text
configs/experiments/3dvar_fgat/runtime_manifest.example.yaml
```

Tool:

```text
tools/prepare_runtime.py
```

Wrapper:

```text
scripts/run/prepare_3dvar_fgat_runtime.sh
```

## Dry-run mode

The default mode is dry-run:

```bash
bash scripts/run/prepare_3dvar_fgat_runtime.sh
```

In dry-run mode, missing required inputs are reported but do not fail the command. This allows local
structural validation on a workstation without JACI data files.

## Strict mode

Use strict mode on JACI or any environment where the required files should exist:

```bash
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
```

In strict mode, missing required files cause an error.

## Copy mode

By default, files are linked using symbolic links. To copy instead:

```bash
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict --copy
```

## Force mode

To replace existing links or files:

```bash
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict --force
```

## Manifest structure

The manifest contains:

```yaml
runtime:
  experiment_name: jaci_3dvar_fgat_smoke
  cycle: "2024081500"
  work_dir: "build/runtime/jaci_3dvar_fgat_smoke/2024081500"
  directories:
    - analysis
    - background
    - feedback
  links:
    - name: background_state
      source: "${MONAN_DATA_ROOT}/background/2024081500/mpasout.2024-08-15_00.00.00.nc"
      target: "background/mpasout.2024-08-15_00.00.00.nc"
      required: true
```

## Current limitations

This layer does not yet:

- render MPAS namelist files;
- render MPAS stream files;
- validate graph partition compatibility with MPI layout;
- check NetCDF/HDF5 schema;
- check JEDI YAML schema;
- submit PBS jobs;
- launch `mpasjedi_variational.x`.

## Development rule

Any new required input for a JEDI task should be represented explicitly in the runtime manifest.
Hidden file assumptions are discouraged.
