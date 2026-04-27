# Configuration Strategy

The configuration is split into five concerns:

| Layer | Directory | Purpose |
|---|---|---|
| Generic workflow | `workflow/`, `scripts/` | orchestration and helper logic |
| MPAS science | `configs/mpas/` | namelists, streams and model controls |
| JEDI science | `configs/jedi/` | variational/HofX templates, observers, SABER/BUMP options |
| Site/HPC | `configs/sites/<site>/` | modules, accounts, queues, paths and MPI launcher |
| Experiment | `configs/experiments/<name>/` | dates, cycle length, DA type and selected resources |

Use YAML for scientific and experiment configuration. Use `.env`/shell files for paths, modules
and machine-specific execution controls.
