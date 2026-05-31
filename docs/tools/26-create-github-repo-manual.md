# 26. create_github_repo_manual.sh

[Back to tools index](../tools.md) | Previous: [run_variational.py](25-run-variational.md) | Next: none

## Purpose

`create_github_repo_manual.sh` records the original manual procedure used to create and bootstrap the GitHub repository.

## Context of use

This script is not part of the scientific workflow. It is provenance for repository setup. Use it only when manually creating the repository from a local tree.

## Location

```text
tools/create_github_repo_manual.sh
```

## Prerequisites

- Bash.
- Git.
- GitHub CLI (`gh`) installed and authenticated.
- A local repository tree ready to publish.
- `docs/pull_request_bootstrap.md` available for the pull request body.

## How to run

```bash
bash tools/create_github_repo_manual.sh
```

## Parameters

The script does not accept command-line parameters. The repository name and branch name are hard-coded in the script.

## Inputs and outputs

The script creates the GitHub repository, configures `origin`, pushes the current source tree, creates a bootstrap branch, commits files, pushes the branch, and opens a pull request.

## Examples

```bash
bash tools/create_github_repo_manual.sh
```

## Common errors

- `gh` is not installed or not authenticated.
- The remote repository already exists.
- The working tree has unexpected state.
- `docs/pull_request_bootstrap.md` is missing.

## Observations

This script should not normally be re-run after the repository exists. Treat it as historical and operational setup documentation.

## Related tools

This script is independent from the runtime and validation tools. It is listed last because it documents repository bootstrap, not experiment execution.

[Back to tools index](../tools.md) | Previous: [run_variational.py](25-run-variational.md) | Next: none
