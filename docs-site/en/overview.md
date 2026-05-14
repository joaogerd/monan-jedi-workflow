# Project overview

## What it is

MONAN-JEDI-WORKFLOW is a workflow layer for MONAN/MPAS and JEDI-MPAS data assimilation experiments. It organizes scripts, configuration files, validation tools and templates required to prepare and execute HPC experiments.

The initial target is a 3DVar-FGAT experiment on JACI using PBS and an external MPAS-JEDI build.

## Problem addressed

Without a workflow layer, experiments often depend on manual commands, local paths, scattered scripts and informal validation. This reduces reproducibility and makes collaboration harder.

The project creates an explicit sequence:

```text
configure environment
prepare data
validate inputs
render JEDI YAML
prepare runtime
render PBS job
submit execution
collect results
```

## Target users

- data assimilation researchers;
- MONAN/JEDI developers;
- INPE HPC users;
- teams testing cycling experiments;
- future workflow maintainers or operators.

## Current status

The project currently supports structural preparation of a first 3DVar-FGAT case. Real scientific execution still depends on valid input data, a working MPAS-JEDI build and validated JEDI observers.
