#!/usr/bin/env bash
set -euo pipefail

repo_name="monan-jedi-workflow"

gh repo create "joaogerd/${repo_name}" \
  --public \
  --description "MONAN/JEDI workflow for MPAS-Atmosphere and JEDI-MPAS cycling experiments on INPE HPC systems" \
  --source . \
  --remote origin \
  --push

git checkout -b bootstrap/inpe-jaci-3dvar-fgat
git add .
git commit -m "Bootstrap MONAN-JEDI workflow structure for JACI"
git push -u origin bootstrap/inpe-jaci-3dvar-fgat

gh pr create \
  --title "Bootstrap MONAN-JEDI-WORKFLOW for JACI 3DVar-FGAT" \
  --body-file docs/pull_request_bootstrap.md \
  --base main \
  --head bootstrap/inpe-jaci-3dvar-fgat
