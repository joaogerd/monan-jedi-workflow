# MONAN-JEDI-WORKFLOW

Initial INPE-oriented migration base derived conceptually from NCAR/MPAS-Workflow.

This repository is intended to evolve into a clean, portable workflow for MONAN/MPAS-JEDI
experiments, initially targeting **3DVar-FGAT** cycling on the **JACI** HPE/Cray supercomputer
using **PBS** and **Cylc 8**.

## Scope

This first version is intentionally conservative:

- documents the original MPAS-Workflow architecture;
- preserves the scientific role of MPAS, JEDI, observation and experiment configurations;
- introduces an INPE/JACI-oriented directory layout;
- adds Bash-first runtime helpers;
- provides PBS and Cylc templates;
- does not claim to replace all original C-shell task scripts in one step.

## Quick start on JACI

```bash
git clone https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow

cp configs/sites/jaci/site.env.example configs/sites/jaci/site.env
${EDITOR:-vi} configs/sites/jaci/site.env

source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
scripts/setup/check_runtime.sh configs/sites/jaci/site.env
```

Configure Cylc:

```bash
mkdir -p "$HOME/.cylc/flow"
cp workflow/cylc/global.cylc.jaci.example "$HOME/.cylc/flow/global.cylc"
```

A real 3DVar-FGAT run requires validated MPAS/JEDI executables, MPAS mesh/static files,
graph partition files, background states, observation files in IODA format, and SABER/BUMP
covariance files.
