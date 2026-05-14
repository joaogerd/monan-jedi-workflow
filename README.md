# MONAN-JEDI-WORKFLOW

Initial INPE-oriented migration base derived conceptually from NCAR/MPAS-Workflow.

This repository is intended to evolve into a clean, portable workflow for MONAN/MPAS-JEDI
experiments, initially targeting **3DVar-FGAT** cycling on the **JACI** HPE/Cray supercomputer
using **PBS**.

## Documentation

A structured bilingual documentation site is available under:

```text
docs-site/
```

The site is built with MkDocs and includes Portuguese and English documentation for project overview,
architecture, installation, usage, cookbook recipes, extension guidelines, developer notes and file
reference.

Preview locally with:

```bash
python3 -m pip install -r requirements-docs.txt
mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000
```

## Scope

This version is intentionally conservative:

- documents the original MPAS-Workflow architecture;
- preserves the scientific role of MPAS, JEDI, observation and experiment configurations;
- introduces an INPE/JACI-oriented directory layout;
- adds Bash-first runtime helpers;
- provides PBS templates;
- adds template-rendering and validation layers;
- does not claim to replace all original C-shell task scripts in one step.

## Quick start on JACI

```bash
git clone https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow

cp configs/sites/jaci/site.env.example configs/sites/jaci/site.env
${EDITOR:-vi} configs/sites/jaci/site.env

source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
bash scripts/setup/check_runtime.sh configs/sites/jaci/site.env
bash tests/smoke_check.sh
```

A real 3DVar-FGAT run requires validated MPAS/JEDI executables, MPAS mesh/static files,
graph partition files, background states, observation files in IODA format, and SABER/BUMP
covariance files.

## Render a 3DVar-FGAT template smoke file

The repository includes a template-rendering layer that can be tested without MPAS/JEDI:

```bash
bash scripts/run/render_3dvar_fgat.sh
```

Default output:

```text
build/rendered/3dvar_fgat.yaml
```

This rendered file is a structural smoke output. It is not yet a validated scientific JEDI
configuration for production use.
