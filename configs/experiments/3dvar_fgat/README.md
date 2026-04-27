# 3DVar-FGAT experiment configuration

This directory contains the first MONAN-JEDI-WORKFLOW experiment target: a deterministic
3DVar-FGAT cycling experiment using MPAS-Atmosphere and JEDI-MPAS on JACI/PBS.

This is currently a **configuration contract**, not a validated scientific experiment.

## Intended first milestone

The first validated milestone is intentionally small:

```text
one cycle
offline background states
offline IODA observations
static SABER/BUMP covariance files
MPAS-JEDI variational executable
no radiance VarBC in the first smoke run
no EDA
no hybrid ensemble covariance
no online observation conversion
no long forecast verification
```

## Required inputs

A real 3DVar-FGAT experiment requires:

| Input | Description |
|---|---|
| MPAS mesh/static files | Mesh and static geographical fields for the selected resolution |
| Graph partition files | Partition files compatible with the selected MPI task count |
| Background states | MPAS states at the required FGAT times inside the assimilation window |
| IODA observations | Observation files with valid timestamps inside the DA window |
| SABER/BUMP covariance files | Static covariance files compatible with variables, mesh and MPI layout |
| MPAS namelist/streams | Runtime MPAS configuration for forecast and variational tasks |
| JEDI application YAML | Variational YAML with correct cost function, geometry, background and observers |

## Configuration separation

The experiment YAML should contain experiment choices, for example:

- experiment name;
- start/end date;
- cycling interval;
- assimilation window;
- selected site;
- selected mesh resource;
- selected observation resource;
- selected covariance resource;
- selected JEDI application template.

It should not hard-code JACI module commands, PBS account settings or absolute NCAR paths.

## 3DVar-FGAT caution

The upstream audit did not identify a dedicated `3dvar_fgat.yaml` template in NCAR/MPAS-Workflow.
The upstream `3dvar.yaml` template uses a 3D-Var cost function with a time window and one background
state template. Therefore the MONAN 3DVar-FGAT implementation must be validated against the exact
MPAS-JEDI version used on JACI.

The key validation questions are:

1. How should multiple background times be represented for FGAT in the selected JEDI-MPAS version?
2. Which MPAS stream outputs are required inside the assimilation window?
3. Does the selected observer set correctly use observation timestamps?
4. Are the background files named and linked in the layout expected by `mpasjedi_variational.x`?

## First run recommendation

Start with conventional observations only, with IODA files already prepared offline. Do not enable
radiance bias correction, EDA, hybrid covariance, online BUFR conversion or extended forecast until
one deterministic 3DVar-FGAT cycle is reproducible.
