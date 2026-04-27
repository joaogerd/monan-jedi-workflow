# JACI site configuration

This directory contains INPE/JACI-specific runtime configuration.

The site layer must answer only site/runtime questions:

- which modules must be loaded;
- where MPAS-JEDI is installed;
- where experiments should run;
- which PBS account and queue should be used;
- which MPI launcher should be used;
- where Cylc should write run directories;
- where static data, meshes, graph files, observations and covariance files are stored.

It must not contain experiment-specific science decisions such as DA type, cycling window,
observation list, minimizer settings or covariance model choices.

## Required files

```text
configs/sites/jaci/
├── site.env.example   # template copied by users to site.env
├── site.env           # local file, not committed
├── modules.sh         # module loading commands for JACI
└── README.md
```

## Local setup

```bash
cp configs/sites/jaci/site.env.example configs/sites/jaci/site.env
${EDITOR:-vi} configs/sites/jaci/site.env
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
scripts/setup/check_runtime.sh configs/sites/jaci/site.env
```

## PBS/Cylc platform

The first JACI target uses PBS through Cylc platform `pbs_cluster`, matching the upstream
MPAS-Workflow convention. This reduces migration risk because upstream task generation assumes a
PBS-style platform in many examples.

The user-level Cylc configuration should be installed as:

```bash
mkdir -p "$HOME/.cylc/flow"
cp workflow/cylc/global.cylc.jaci.example "$HOME/.cylc/flow/global.cylc"
```

## Site variables expected by scripts

| Variable | Meaning |
|---|---|
| `MONAN_SITE` | Site identifier, expected to be `jaci` |
| `MONAN_PROJECT` | PBS project/account |
| `MONAN_QUEUE` | PBS queue |
| `MONAN_WORK_ROOT` | Persistent work directory |
| `MONAN_SCRATCH` | Scratch/run directory |
| `MPAS_BUNDLE_BUILD` | Build/install directory containing MPAS/JEDI executables |
| `MPAS_ATMOSPHERE_EXE` | MPAS-Atmosphere executable path |
| `MPASJEDI_VARIATIONAL_EXE` | JEDI-MPAS variational executable path |
| `MPASJEDI_HOFX_EXE` | JEDI-MPAS HofX executable path |
| `MPI_LAUNCHER` | MPI launcher command, e.g. `mpiexec` |
| `CYLC_PLATFORM` | Cylc platform name, initially `pbs_cluster` |

## Validation rule

A JACI site configuration is considered usable only when:

```bash
scripts/setup/check_runtime.sh configs/sites/jaci/site.env
```

passes on a JACI login node and a PBS smoke test can be submitted successfully.
