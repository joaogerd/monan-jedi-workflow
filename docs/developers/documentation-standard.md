# Documentation Standard

## Scope

This standard applies to public Python APIs, command-line interfaces, YAML configuration, Markdown pages, examples, user-facing error messages, and generated workflow documentation.

All public documentation must be written in English.

## Python Docstrings

Public functions, classes, methods, and modules must use NumPy-style docstrings. A public docstring must describe parameters, returns, raised exceptions, assumptions, and scientific notes when relevant.

Docstrings describe current observable behavior. They must not describe behavior that is planned but not implemented.

## Inline Comments

Use inline comments for non-obvious logic, scientific conventions, compatibility constraints, data-layout transformations, performance choices, and safety checks.

Comments must explain why a decision exists. Do not repeat a statement already obvious from the code.

## Markdown Tool Pages

Each user-facing component or stage must have one Markdown page under `docs/tools/` with these sections:

1. Purpose
2. Scientific context
3. When to use the tool
4. Inputs
5. Outputs
6. Artifact contract
7. YAML configuration
8. Parameters
9. Dependencies
10. CLI usage
11. simpleWorkflow usage
12. ecFlow and Cylc integration contract
13. Validation
14. Restart and idempotency behavior
15. Limitations
16. FAQ
17. References

## Configuration Documentation

Every user-facing YAML key must document its path, type, default value, accepted values or range, units when applicable, scientific or operational effect, and invalidation behavior for existing products.

Every run must save its resolved configuration.

## Documentation and Code Consistency

Documentation is executable evidence and must be checked against implementation.

Continuous integration must verify:

- public APIs have required docstrings;
- documented CLI commands are available through `--help`;
- documented YAML examples validate against the runtime schema;
- executable command examples run in fixture or dry-run mode;
- documented artifact contracts match inspected output files;
- generated configuration reference material is derived from the runtime schema.

A documentation claim that is not covered by implementation or tests must be rejected during review.

## Review Checklist

Before merging a stage or tool change, reviewers must confirm that docstrings reflect current behavior, documented parameters exist in the schema and implementation, examples use current commands and YAML keys, output paths match generated workspaces, limitations are explicit, and inline comments explain non-obvious decisions.