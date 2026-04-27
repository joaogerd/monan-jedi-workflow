# Migration Notes from NCAR/MPAS-Workflow

## Preserved concepts

- Cylc as workflow engine.
- Scenario-driven execution.
- Separate forecast, variational, HofX and verification task families.
- MPAS/JEDI templates are scientific configuration and must not be discarded.
- PBS is a first-class target because both Derecho and JACI use PBS-style submission.

## NCAR-specific elements to isolate

- `/glade/...` paths.
- Derecho-specific environment variables.
- NCAR account/project names.
- NCAR-specific observation archives.
- NCAR-specific BUMP/SABER covariance paths.
- hard-coded C-shell environment generation.

## Initial MONAN simplification

- Put all site paths in `configs/sites/jaci/site.env`.
- Put first experiment in `configs/experiments/3dvar_fgat/experiment.yaml`.
- Use Bash wrappers for new functionality.
- Preserve legacy C-shell behavior as reference until each task is ported and tested.
