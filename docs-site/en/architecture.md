# System architecture

## Core principle

MONAN-JEDI-WORKFLOW is designed to avoid a monolithic workflow. Each layer has a clear responsibility:

```text
configs/      scientific, site and experiment configuration
scripts/      user-facing setup and run commands
tools/        Python validation, rendering and audit tools
jobs/         PBS job templates
workflow/     future orchestration layer, such as Cylc or ecFlow
docs/         historical technical documentation
docs-site/    navigable MkDocs website
```

## Responsibility split

| Layer | Responsibility |
|---|---|
| `configs/sites/` | HPC environment, modules, queues, paths and executables |
| `configs/experiments/` | Experiment cycle, data, observers and staging configuration |
| `configs/mpas/` | MONAN/MPAS-related configuration |
| `configs/jedi/` | JEDI templates, observers and metadata |
| `scripts/setup/` | Preparation, bootstrap, checks and staging |
| `scripts/run/` | Rendering, runtime preparation and execution steps |
| `tools/` | Reusable Python logic |
| `jobs/pbs/` | PBS submission templates |
| `workflow/` | Future task orchestration |

## JEDI and MONAN/MPAS relation

JEDI-MPAS performs data assimilation and produces an analysis. MONAN/MPAS should then run a short forecast from that analysis to provide the background for the next cycle.

```text
background + observations
        ↓
   JEDI 3DVar-FGAT
        ↓
      analysis
        ↓
   MONAN/MPAS forecast
        ↓
background for the next cycle
```

## Cylc and ecFlow

The project was inspired by NCAR MPAS-Workflow, which uses Cylc. However, the core logic should remain independent of any specific orchestrator. A future `workflow/ecflow/` layer can call the same setup and run scripts currently used by shell or Cylc workflows.

## Integration with MONAN forecast scripts

If the MONAN group already has scripts to run the model, they should be integrated through wrappers. The workflow should rely on input/output contracts, not on the internal implementation of those scripts.
