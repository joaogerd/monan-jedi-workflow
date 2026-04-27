# Architecture

## Original MPAS-Workflow model

NCAR/MPAS-Workflow is organized around four layers:

1. **Scenario YAML** files define experiments.
2. **Python initialization** code parses scenario nodes and generates Cylc runtime files.
3. **Cylc 8** orchestrates task dependencies and job submission.
4. **Task shell scripts**, mostly C-shell, execute MPAS-Atmosphere, MPAS-JEDI and utilities.

The original `Run.py` parses a scenario, generates Cylc-related files, creates `config/auto/*.csh`,
builds a `suite.rc`, and initiates the Cylc suite through `submit.csh`.

## MONAN-JEDI-WORKFLOW target model

```text
configs/sites/        site/HPC configuration
configs/experiments/  experiment-level scientific choices
configs/mpas/         MPAS-Atmosphere namelist/stream/template controls
configs/jedi/         JEDI-MPAS application and observation templates
workflow/cylc/        Cylc suite templates and global examples
workflow/tasks/       workflow task wrappers
jobs/pbs/             PBS job templates
scripts/env/          environment loading
scripts/setup/        sanity checks and bootstrap scripts
scripts/run/          user-facing run commands
```

## Migration rule

Do not delete scientific configuration until its role is understood. Legacy NCAR-specific paths
should be isolated, not silently removed.
