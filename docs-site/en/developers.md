# Developer documentation

## Repository organization

```text
configs/       YAML and shell configuration
docs/          historical technical documentation
docs-site/     MkDocs web documentation
jobs/          submission templates
scripts/       setup and run commands
tests/         structural smoke tests
tools/         Python tools
workflow/      orchestration tasks and templates
```

## Conventions

- Bash scripts should use clear logging and predictable error handling.
- Scripts that are sourced must preserve the caller shell state.
- Python tools should fail with clear messages.
- Real scientific data must not be committed to Git.
- Example files should use `.example.yaml` when they are not final operational configuration.

## Contribution flow

```bash
git checkout main
git pull
git checkout -b feature/my-change
# edit files
git add .
git commit -m "Clear commit message"
git push -u origin feature/my-change
```

Open a Pull Request describing the goal, changed files, validation commands, risks and next steps.

## Branch strategy

Use small, focused branches. Avoid mixing documentation, runtime logic and scientific configuration changes in the same PR unless necessary.

## Traceability

Operational changes should include documentation and validation evidence, especially when tested on JACI.
