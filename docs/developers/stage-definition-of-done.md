# Stage Definition of Done

## Purpose

A stage is not complete because it exits successfully once. A stage is complete only when its implementation, validation, documentation, configuration, and artifact contracts have been verified.

## Required Interface

Every executable stage must expose the same lifecycle where applicable:

```text
plan
prepare
validate-inputs
submit
wait
status
validate-output
finalize
```

A stage may omit a scheduler action only when it is intentionally local and synchronous. The reason must be documented.

## Implementation

- [ ] The implementation is located in the correct component package.
- [ ] The workflow only composes stages and does not duplicate component logic.
- [ ] The public API uses NumPy-style docstrings.
- [ ] Non-obvious scientific and technical decisions have inline comments.
- [ ] The stage has no implicit dependency on the current directory, shell state, or undocumented environment variables.
- [ ] The stage can be invoked directly through the project CLI.

## Configuration

- [ ] A simple user-facing case configuration exists.
- [ ] Advanced configuration is separated into site, profile, science, or workflow files.
- [ ] All public configuration keys are schema-validated and documented.
- [ ] A resolved configuration is written into the run workspace.
- [ ] Configuration changes that invalidate products are identified.

## Artifacts and Provenance

- [ ] Every input and output has an explicit artifact contract.
- [ ] Required file format, NetCDF structure, variables, dimensions, attributes, and time conventions are validated.
- [ ] Producer and consumer stages are identified.
- [ ] Checksums or equivalent integrity records are written where applicable.
- [ ] The run records code revision, resolved configuration, input manifest, environment, and command line.

## Validation

- [ ] Unit tests cover domain logic and failure modes.
- [ ] Integration tests cover the stage lifecycle with fixtures.
- [ ] A real JACI execution has been validated.
- [ ] Output validation checks both file presence and semantic structure.
- [ ] Scientific comparison against a trusted reference is completed when applicable.
- [ ] The stage is idempotent and can resume safely after interruption.

## Documentation

- [ ] A complete English Markdown page exists under `docs/tools/`.
- [ ] The page includes objective, inputs, outputs, artifact contract, parameters, dependencies, examples, validation, restart behavior, limitations, FAQ, and references.
- [ ] Public APIs have NumPy-style docstrings.
- [ ] Inline comments explain non-obvious code decisions.
- [ ] CLI examples and YAML examples are verified in CI.
- [ ] Documentation has been checked against the generated workspace and current source code.

## Orchestration

- [ ] The stage is usable by the local adapter.
- [ ] The stage contract is usable by the simpleWorkflow adapter.
- [ ] The dependency and artifact contract are sufficient for future ecFlow and Cylc adapters.

## Final Validation Evidence

At the end of each stage, an independent validation pass must inspect the pull request, run the documented local tests and dry-run examples, check artifact contracts and restart behavior, and compare documentation with source code.

For JACI-capable stages, the evidence must include the documented JACI dry-run and the smallest real PBS smoke test. Scheduler completion alone is insufficient; the declared output contract must validate.

When a trusted scientific reference exists, the evidence must include the comparison method, tolerance, and result. The recorded validation summary must include the commit SHA, PR number, commands and exit codes, resolved configuration path, artifact locations, tests, JACI job identifiers when applicable, known limitations, and one final status: `complete`, `blocked`, or `needs-fixes`.

## Completion Rule

A stage is marked complete only after every applicable checkbox is satisfied and the final validation evidence is recorded in its documentation page or validation record. A stage marked `blocked` or `needs-fixes` cannot be followed by the next scientific stage.
