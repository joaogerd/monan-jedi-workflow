## Summary

<!-- Describe what this PR changes and why. Keep the scope small and explicit. -->

## Type of change

<!-- Mark the relevant items with x. -->

- [ ] config
- [ ] test
- [ ] docs
- [ ] ci
- [ ] runtime/staging
- [ ] renderer
- [ ] other

## Validation

<!-- Mark what was done. -->

- [ ] I ran `python -m pytest` locally.
- [ ] I checked the rendered YAML when this PR changes configuration or rendering.
- [ ] I checked the rendered PBS when this PR changes scheduler-related configuration.
- [ ] I did not run local tests; reason:

## Operational safety

<!-- These rules protect the JACI/MONAN operational workflow. -->

- [ ] This PR does not submit jobs automatically.
- [ ] This PR does not call `qsub`, `mpiexec`, `mpirun`, or `mpasjedi_variational.x` automatically.
- [ ] This PR does not version large data, logs, model outputs, or generated `build/` artifacts.

## Configuration fragments

<!-- Required only when this PR changes experiment configuration. -->

- [ ] Reused existing fragments where possible.
- [ ] Added new fragments only when needed.
- [ ] Avoided duplicating long variable or observer lists inside experiment directories.
- [ ] Not applicable.

## Notes

<!-- Mention limitations, follow-up work, or anything reviewers should know. -->
