---
name: Bug report
description: Report an error in validation, rendering, runtime preparation, or CI
title: "bug: "
labels: ["bug"]
assignees: []
---

## Summary

Describe the problem clearly and briefly.

## Where did it fail?

Mark the relevant item:

- [ ] `validate-config`
- [ ] `render-yaml`
- [ ] `render-pbs`
- [ ] `prepare-runtime`
- [ ] CI / GitHub Actions
- [ ] Documentation
- [ ] Other

## Command or action

Paste the command that failed, if applicable.

```bash

```

## Error output

Paste the relevant traceback, log excerpt, or CI output.

```text

```

## Expected behavior

Describe what should have happened.

## Environment

- Operating system:
- Python version:
- Branch or commit:
- Experiment config directory:

## Operational safety

Confirm the report does not require automatic job submission:

- [ ] This issue does not request automatic `qsub`, `mpiexec`, `mpirun`, or `mpasjedi_variational.x` execution.

## Additional context

Add any relevant notes, links, screenshots, or files.
