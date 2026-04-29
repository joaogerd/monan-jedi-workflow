# JACI site environment

This document explains how to configure the JACI site environment for MONAN-JEDI-WORKFLOW.

The active site file is intentionally not committed:

```text
configs/sites/jaci/site.env
```

Create it from the example:

```bash
cp configs/sites/jaci/site.env.example configs/sites/jaci/site.env
${EDITOR:-vi} configs/sites/jaci/site.env
```

## Required variables

| Variable | Purpose |
|---|---|
| `MONAN_PROJECT` | PBS account/project allocation |
| `MONAN_QUEUE` | PBS queue |
| `MONAN_WORKFLOW_ROOT` | Absolute path to the repository checkout on JACI |
| `MONAN_WORK_ROOT` | Persistent work area |
| `MONAN_SCRATCH` | Scratch/runtime area |
| `MONAN_DATA_ROOT` | Root for experiment input data |
| `MPAS_BUNDLE_BUILD` | Build or install directory of the selected MPAS-JEDI bundle |
| `MPASJEDI_VARIATIONAL_EXE` | Path to `mpasjedi_variational.x` |
| `MPI_LAUNCHER` | MPI launcher command for JACI |
| `CYLC_PLATFORM` | Cylc platform name, initially `pbs_cluster` |

## Python on JACI

The default `python3` available before loading Anaconda may be too old for the repository tools.
One observed symptom is:

```text
SyntaxError: future feature annotations is not defined
```

Before running Python-based validation tools on JACI, load Anaconda and initialize Conda:

```bash
module load anaconda
start_conda
```

In this repository, that startup is centralized in:

```text
configs/sites/jaci/modules.sh
```

The environment loader calls this file automatically.

## Load environment

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

This should load the Anaconda module, run `start_conda`, and expose a newer Python runtime.

## Check environment

```bash
bash scripts/setup/check_runtime.sh configs/sites/jaci/site.env
```

The check script reports missing commands, missing executables and missing data directories as
warnings. Review all warnings before running a scientific experiment.

## Expected JACI workspace

The observed workspace during validation was:

```text
/p/projetos/monan_das/joao.gerd
```

The default example therefore uses:

```text
${MONAN_JACI_WORKSPACE}/projects/monan-jedi-workflow
```

for the repository checkout.

## Expected data layout

The current smoke workflow expects a structure similar to:

```text
${MONAN_DATA_ROOT}/
├── background/2024081500/
├── observations/ioda/2024081500/
├── covariance/
├── graph/
└── static/
```

The exact scientific files must be provided by the experiment setup and must match the selected
mesh, MPAS-JEDI version, MPI layout and covariance resources.

## Important caution

The example values are placeholders. Do not submit PBS jobs until:

1. `MONAN_PROJECT` and `MONAN_QUEUE` are confirmed for JACI;
2. `MPAS_BUNDLE_BUILD` points to a validated MPAS-JEDI build;
3. `MPASJEDI_VARIATIONAL_EXE` exists and is executable;
4. `MPI_LAUNCHER` is confirmed for JACI;
5. background, observations, covariance, graph and static files exist;
6. the rendered JEDI YAML has been inspected.
