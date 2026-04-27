# Upstream configuration map

This document maps the main configuration files from `NCAR/MPAS-Workflow` into the new
MONAN-JEDI-WORKFLOW architecture.

The purpose is to avoid two common mistakes:

1. deleting scientifically important configuration files because they look like site-specific examples;
2. copying NCAR/Derecho configuration directly into INPE/JACI experiments.

## 1. Configuration categories

| Category | Meaning | MONAN location |
|---|---|---|
| Generic workflow configuration | Defines task graph, task types, Cylc behavior and reusable runtime rules | `workflow/` |
| MPAS scientific configuration | Controls MPAS namelists, streams, mesh-dependent model settings and model variables | `configs/mpas/` |
| JEDI scientific configuration | Controls JEDI applications, observers, cost function, covariance and variable changes | `configs/jedi/` |
| Site configuration | Defines modules, filesystem paths, scheduler, MPI launcher and account/queue rules | `configs/sites/<site>/` |
| Experiment configuration | Defines dates, DA type, cycling window, selected resources and experiment-specific paths | `configs/experiments/<experiment>/` |
| Job templates | Scheduler-specific launch wrappers | `jobs/pbs/`, later `jobs/slurm/` |

## 2. MPAS configuration from upstream

| Upstream file/directory | Function | MONAN migration decision |
|---|---|---|
| `scenarios/defaults/model.yaml` | Mesh/resource defaults: mesh ratio, number of cells, timestep, diffusion length, physics suite and parameterization choices | Import concepts; split into generic mesh resources and site-specific path bindings |
| `config/mpas/geovars.yaml` | Geophysical variables available to UFO through MPAS-JEDI | Preserve with provenance; validate against selected MPAS-JEDI version |
| `config/mpas/variables.csh` | State, analysis and control variable lists used during JEDI YAML generation | Convert to `configs/mpas/variables.yaml` only after confirming substitution logic |
| `config/mpas/forecast/*` | MPAS namelist/streams for forecast tasks | Preserve templates; remove hard-coded paths |
| `config/mpas/variational/*` | MPAS namelist/streams for variational tasks | Preserve templates; required for 3DVar/FGAT |
| `config/mpas/hofx/*` | MPAS namelist/streams for HofX tasks | Preserve later; not mandatory for first 3DVar-FGAT smoke run |
| `config/mpas/initic/*` | Configuration for external analysis to MPAS IC generation | Preserve as later phase; avoid first-run dependency |

## 3. JEDI configuration from upstream

| Upstream file/directory | Function | MONAN migration decision |
|---|---|---|
| `config/jedi/applications/3dvar.yaml` | Main MPAS-JEDI 3DVar template using SABER/BUMP and observers inserted by workflow | Preserve and adapt for MONAN 3DVar baseline |
| `config/jedi/applications/hofx.yaml` | HofX application template | Preserve later; useful for verification and obs-space diagnostics |
| `config/jedi/applications/*envar*` | EnVar/hybrid templates | Preserve only after 3DVar-FGAT baseline is stable |
| `config/jedi/ObsPlugs/variational/*.yaml` | Observation stubs inserted into variational applications | Essential; import selected conventional observation plugs first |
| `config/jedi/ObsPlugs/hofx/*.yaml` | Observation stubs inserted into HofX applications | Later phase |
| `scenarios/defaults/variational.yaml` | Covariance, localization, ensemble resources and job sizing | Split scientific covariance resources from site resource sizing |
| `scenarios/defaults/observations.yaml` | Observation resources, IODA directories, prefixes and bias-correction eligibility | Preserve structure; replace `/glade` paths with JACI/local resources |

## 4. Runtime and task scripts from upstream

| Upstream script | Function | Bash migration priority |
|---|---|---|
| `bin/PrepJEDI.csh` | Prepares JEDI YAMLs, inserts observers, prepares MPAS namelist/streams, links invariant and graph files | Very high; but convert only after tests |
| `bin/Forecast.csh` | Runs MPAS-Atmosphere forecasts | High |
| `bin/Variational.csh` | Runs `mpasjedi_variational` | High |
| `bin/HofX.csh` | Runs `mpasjedi_hofx3d` | Medium |
| `bin/ObsToIODA.csh` | Converts BUFR/PrepBUFR to IODA | Medium/low for first phase; start with offline IODA |
| `bin/VerifyObs.csh` | Observation-space verification | Later phase |
| `bin/VerifyModel.csh` | Model-space verification | Later phase |
| `bin/getCycleVars.csh` | Defines cycle-specific date variables and directories | Replace early with Bash/Python date utilities |
| `submit.csh` | Submits generated Cylc suite | Replace with Bash/Cylc wrapper |

## 5. 3DVar-FGAT observation

No explicit upstream `3dfgat.yaml` or `3dvar_fgat.yaml` template was identified during the first audit.
Therefore, MONAN-JEDI-WORKFLOW treats 3DVar-FGAT as a controlled extension of the upstream
`3dvar.yaml` / `Variational` path.

The first implementation must verify:

- how MPAS-JEDI expects FGAT states in the selected bundle version;
- whether multiple background files are referenced through state geometry/time window configuration;
- how `window begin` and `window length` interact with observation timestamps;
- whether MPAS streams generate all required background states inside the assimilation window.

Until this is validated on JACI, `configs/jedi/applications/3dvar_fgat.yaml` must be considered a
placeholder, not a scientifically validated template.

## 6. JACI migration rule

A file is ready for JACI only when all of the following are true:

- no `/glade` path remains in active experiment configuration;
- the PBS account, queue and filesystem paths come from `configs/sites/jaci/site.env`;
- MPAS/JEDI executables are resolved from `MPAS_BUNDLE_BUILD` or explicit site variables;
- MPI launcher is site-controlled;
- graph partition files and covariance files are explicitly configured for the selected mesh and MPI layout.
