---
name: Experiment request
description: Request support for a new experiment, cycle, mesh, observation set, or covariance option
title: "experiment: "
labels: ["experiment"]
assignees: []
---

## Objective

Describe the experiment or workflow extension requested.

## Baseline relationship

How does this request relate to the current baseline?

- [ ] Same 3D-FGAT + MPASstatic method
- [ ] New cycle/date
- [ ] New mesh
- [ ] New observation set
- [ ] New variable set
- [ ] New covariance option
- [ ] New runtime/HPC environment
- [ ] Other

## Proposed configuration

Fill in what is known.

- Experiment name:
- Cycle:
- Mesh:
- Number of MPI ranks:
- Covariance model:
- Observation fragments:
- Variable fragment:
- Runtime data root:

## Required fragments

List existing fragments that can be reused, or new fragments that may be needed.

```text
variables:
observers:
```

## Validation criteria

How should we know this experiment is correctly configured?

- [ ] `validate-config` passes.
- [ ] `render-yaml` produces the expected MPAS-JEDI YAML.
- [ ] `render-pbs` produces the expected scheduler script.
- [ ] Manual runtime staging has been reviewed.
- [ ] Manual MPAS-JEDI execution has been performed outside CI, if needed.

## Operational safety

- [ ] This request does not require automatic scheduler submission.
- [ ] Any `qsub`, `mpiexec`, `mpirun`, or `mpasjedi_variational.x` execution will be manual and explicit.

## Additional context

Add paths, logs, references, or links to previous manual tests.
