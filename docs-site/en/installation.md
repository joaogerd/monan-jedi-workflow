# Installation and configuration

## Requirements

On JACI, users need access to:

- Bash;
- Git;
- environment modules;
- Anaconda module and `start_conda`;
- PBS commands such as `qsub` and `qstat`;
- `mpiexec`;
- Python 3 through Anaconda;
- a working MPAS-JEDI build for real execution.

## Clone the repository

```bash
cd /p/projetos/monan_das/$USER/projects
git clone https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
```

## Configure JACI

```bash
cp configs/sites/jaci/site.env.example configs/sites/jaci/site.env
vi configs/sites/jaci/site.env
```

Important variables include:

```bash
MONAN_WORKFLOW_ROOT
MONAN_DATA_ROOT
MONAN_EXTERNAL_DATA_ROOT
MONAN_SCRATCH
MONAN_QUEUE
MPAS_BUNDLE_BUILD
MPASJEDI_VARIATIONAL_EXE
MPI_LAUNCHER
```

## Load the environment

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

## Validate runtime

```bash
bash scripts/setup/check_runtime.sh configs/sites/jaci/site.env
bash tests/smoke_check.sh
```

Warnings about missing scientific data or missing MPAS-JEDI executables are expected before the first real experiment.
