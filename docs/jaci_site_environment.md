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

## Runtime model

MONAN-JEDI-WORKFLOW does not build MPAS-JEDI. It consumes executables produced by
the MONAN-JEDI build. Therefore, runtime PBS jobs must load the same
spack-stack-inpe environment used to compile the selected executable.

The environment loading order is:

1. source `configs/sites/jaci/site.env`;
2. load the selected spack-stack-inpe JACI runtime when `MONAN_LOAD_STACK=true`;
3. load Anaconda when `MONAN_LOAD_ANACONDA=true`;
4. expose MPAS-JEDI executables and the MPI launcher to workflow scripts.

This is centralized in:

```text
configs/sites/jaci/modules.sh
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
| `MONAN_LOAD_STACK` | Whether to load the MONAN-JEDI/spack-stack-inpe runtime |
| `STACK_ROOT` | Root of the selected spack-stack-inpe installation |
| `STACK_ENV_NAME` | Name of the selected stack environment |
| `STACK_MODULE_ROOT` | Module root for the selected stack environment |
| `STACK_ENV_MODULE` | Stack environment module to load |
| `STACK_SITE_SETUP` | Site setup script from spack-stack-inpe |
| `MPAS_BUNDLE_BUILD` | Build or install directory of the selected MPAS-JEDI bundle |
| `MPASJEDI_VARIATIONAL_EXE` | Path to `mpasjedi_variational.x` |
| `MPI_LAUNCHER` | MPI launcher command for JACI |
| `MPI_TASKS_FLAG` | MPI task-count flag used by the selected launcher |
| `CYLC_PLATFORM` | Cylc platform name, initially `pbs_cluster` |

## JACI MPI launcher

The JACI PBS examples use `mpirun -np` after loading the Cray MPI/PALS modules.
For this reason, the JACI example uses:

```bash
export MPI_LAUNCHER="mpirun"
export MPI_TASKS_FLAG="-np"
```

The task-count flag remains configurable because other platforms may use a
different launcher syntax, such as `mpiexec -n` or `srun -n`.

## Python on JACI

The default `python3` available before loading Anaconda may be too old for the repository tools.
One observed symptom is:

```text
SyntaxError: future feature annotations is not defined
```

The repository therefore supports loading Anaconda after the stack runtime:

```bash
export MONAN_LOAD_ANACONDA="true"
```

The stack setup is loaded first because it may reset the module state. Anaconda is
loaded second so the helper scripts run with the expected Python runtime.

## Load environment

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

This should load the selected stack runtime, initialize Anaconda, expose the
selected MPAS-JEDI executables and report the active MPI launcher.

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

The current tutorial workflow expects a structure similar to:

```text
${MONAN_DATA_ROOT}/
├── background/2018041500/
├── observations/ioda/2018041500/
├── covariance/
├── graph/
└── static/
```

The exact scientific files must be provided by the experiment setup and must match the selected
mesh, MPAS-JEDI version, MPI layout and covariance resources.

## Important caution

The example values are placeholders. Do not submit PBS jobs until:

1. `MONAN_PROJECT` and `MONAN_QUEUE` are confirmed for JACI;
2. `STACK_ROOT`, `STACK_MODULE_ROOT`, `STACK_ENV_MODULE` and `STACK_SITE_SETUP` match the stack used to compile MONAN-JEDI;
3. `MPAS_BUNDLE_BUILD` points to a validated MPAS-JEDI build;
4. `MPASJEDI_VARIATIONAL_EXE` exists and is executable;
5. `MPI_LAUNCHER` and `MPI_TASKS_FLAG` are confirmed for JACI;
6. background, observations, covariance, graph and static files exist;
7. the rendered JEDI YAML has been inspected.
