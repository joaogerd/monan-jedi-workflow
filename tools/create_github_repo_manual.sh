#!/usr/bin/env bash
# =============================================================================
# Manually create and bootstrap the MONAN-JEDI workflow GitHub repository.
# =============================================================================
#
# Purpose
# -------
# This helper records the original manual GitHub bootstrap procedure used for the
# MONAN-JEDI workflow repository. It creates the remote repository with the
# GitHub CLI, pushes the current local tree, creates the bootstrap branch, commits
# the initial workflow structure, and opens the bootstrap pull request.
#
# Notes
# -----
# This script is intentionally simple and operational. It assumes that:
#
#   * the GitHub CLI command ``gh`` is installed and authenticated;
#   * the current directory is the local repository root;
#   * the local tree contains the files that should be committed;
#   * ``docs/pull_request_bootstrap.md`` exists and contains the PR body;
#   * the remote repository ``joaogerd/monan-jedi-workflow`` does not already
#     exist, unless the user intentionally wants ``gh repo create`` to fail.
#
# The script is not used by the scientific workflow at runtime. It is retained as
# provenance for repository setup and should be executed manually only when the
# repository has not yet been created.
#
# Examples
# --------
# Run from the repository root after authenticating with GitHub CLI:
#
#   bash tools/create_github_repo_manual.sh
#
# =============================================================================

set -euo pipefail

# Repository name is kept in a variable so the owner/repository string below is
# easier to review and adjust if the workflow is cloned for another namespace.
repo_name="monan-jedi-workflow"

# Create the GitHub repository from the current directory, configure ``origin``,
# and push the current branch. This is the initial publication step.
gh repo create "joaogerd/${repo_name}" \
  --public \
  --description "MONAN/JEDI workflow for MPAS-Atmosphere and JEDI-MPAS cycling experiments on INPE HPC systems" \
  --source . \
  --remote origin \
  --push

# Create a dedicated bootstrap branch so the initial repository structure can be
# reviewed through a pull request instead of being developed directly on main.
git checkout -b bootstrap/inpe-jaci-3dvar-fgat
git add .
git commit -m "Bootstrap MONAN-JEDI workflow structure for JACI"
git push -u origin bootstrap/inpe-jaci-3dvar-fgat

# Open the bootstrap pull request using the prepared PR body. Keeping the body in
# a tracked Markdown file makes the initial review message reproducible.
gh pr create \
  --title "Bootstrap MONAN-JEDI-WORKFLOW for JACI 3DVar-FGAT" \
  --body-file docs/pull_request_bootstrap.md \
  --base main \
  --head bootstrap/inpe-jaci-3dvar-fgat
