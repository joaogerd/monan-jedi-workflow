# JACI Setup

## Required software

- Bash
- Python 3
- Cylc 8
- PBS command-line tools (`qsub`, `qstat`, `qdel`)
- MPAS-Atmosphere executable
- JEDI-MPAS executables from `mpas-bundle`
- NetCDF/HDF5/MPI runtime libraries
- NCO/CDO as needed by task scripts

## Recommended Cylc configuration

```bash
mkdir -p "$HOME/.cylc/flow"
cp workflow/cylc/global.cylc.jaci.example "$HOME/.cylc/flow/global.cylc"
```

## Runtime validation

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
scripts/setup/check_runtime.sh configs/sites/jaci/site.env
```

## PBS validation

```bash
qsub jobs/pbs/smoke_test.pbs
```
