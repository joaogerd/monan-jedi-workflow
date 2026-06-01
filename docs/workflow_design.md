# MONAN-JEDI workflow design principles

This document defines the operational boundary between login-node orchestration and compute-node execution in MONAN-JEDI workflows.

The main rule is simple:

> PBS scripts are execution wrappers, not workflow orchestrators.

A PBS job should be small, deterministic and focused on running one computational step. Configuration, rendering, staging, validation and post-processing should be handled outside the PBS job unless there is a clear technical reason to execute them on compute nodes.

## Responsibility split

### Login node

The login node is responsible for workflow orchestration. It may execute lightweight preparation tasks, file checks and metadata generation.

Typical login-node responsibilities are:

- loading site configuration;
- rendering YAML, namelists, streams and PBS files;
- validating input availability and file formats;
- copying, linking or staging input files;
- downloading or locating external data;
- converting observations when the conversion is treated as a preparation step;
- preparing runtime directories;
- submitting PBS jobs;
- collecting logs after execution;
- running provenance analysis and generating summaries.

The login node should answer the question: **is the runtime ready to execute?**

### Compute node

The compute node is responsible for running the computational payload. A PBS script should not become a second workflow engine.

Typical compute-node responsibilities are:

- loading the minimum runtime environment required by the executable;
- moving to the prepared runtime directory;
- setting runtime variables such as MPI, OpenMP and endian settings;
- checking that the executable exists;
- executing the model, observation converter, assimilation system or heavy validation task;
- writing stdout/stderr to the configured job log.

The compute node should answer the question: **can this prepared executable run successfully on allocated resources?**

## Stage model

The MONAN workflow should be organized into explicit stages. Each stage has a login-node preparation part and, when needed, a compute-node execution part.

### 1. Model stage

Login node:

- prepare model configuration;
- render namelists and streams;
- stage static, boundary and initial condition files;
- validate paths and basic file formats;
- render the model PBS job.

Compute node:

- load the runtime environment;
- enter the prepared model runtime directory;
- run the model executable, for example `mpas_atmosphere`;
- write model logs and outputs.

### 2. Observation stage

Login node:

- locate, download or copy raw observations;
- stage raw files such as PREPBUFR or BUFR;
- validate raw observation availability;
- run lightweight conversion when appropriate;
- validate generated IODA files.

Compute node, only when observation conversion is heavy enough to require allocated resources:

- load the converter runtime environment;
- enter the prepared observation runtime directory;
- run the converter, for example `obs2ioda-v3`;
- write converter logs and outputs.

For the current 3DVar-FGAT tutorial case, the PREPBUFR file is already available and `obs2ioda-v3` is run as a preparation step before assimilation validation.

### 3. Assimilation stage

Login node:

- render the JEDI YAML;
- validate the assimilation window;
- validate background, observation, covariance, graph and static files;
- validate variable mappings;
- prepare the runtime directory;
- render and submit the PBS job.

Compute node:

- load the runtime environment;
- enter the prepared assimilation runtime directory;
- run `mpasjedi_variational.x` or another assimilation executable;
- write the JEDI log and PBS stdout/stderr.

### 4. Validation stage

Login node:

- inspect job logs;
- validate output files;
- run provenance analysis;
- generate summary reports.

Compute node, only for heavy or parallel validation:

- load the runtime environment;
- run the heavy validation executable or script;
- write validation logs and products.

## PBS design rule

A PBS file should normally contain only:

1. PBS directives;
2. `set -euo pipefail`;
3. static variables rendered by the login-node workflow;
4. a site environment load command;
5. runtime environment exports;
6. `cd` into the runtime directory;
7. a small executable existence check;
8. the final execution command.

A minimal assimilation PBS job should resemble:

```bash
#!/usr/bin/env bash
#PBS -N monan_3dvar_fgat
#PBS -q pesqmini
#PBS -l select=1:ncpus=64:mpiprocs=64
#PBS -l walltime=00:30:00
#PBS -j oe
#PBS -o /path/to/runtime/logs/3dvar_fgat.pbs.log

set -euo pipefail
umask 002

REPO_ROOT="/path/to/monan-jedi-workflow"
SITE_ENV="${REPO_ROOT}/configs/sites/jaci/site.env"
RUNTIME_DIR="${REPO_ROOT}/build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500"
YAML_FILE="${REPO_ROOT}/build/rendered/3dvar_fgat.yaml"
MPASJEDI_VARIATIONAL_EXE="/path/to/build/bin/mpasjedi_variational.x"
MPI_TASKS="64"

source "${REPO_ROOT}/scripts/env/load_jaci_env.sh" "${SITE_ENV}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OOPS_TRACE="${OOPS_TRACE:-0}"
export OOPS_DEBUG="${OOPS_DEBUG:-0}"
export GFORTRAN_CONVERT_UNIT="${GFORTRAN_CONVERT_UNIT:-big_endian:101-200}"
export F_UFMTENDIAN="${F_UFMTENDIAN:-big:101-200}"
export FI_CXI_RX_MATCH_MODE="${FI_CXI_RX_MATCH_MODE:-hybrid}"

cd "${RUNTIME_DIR}"

if [[ ! -x "${MPASJEDI_VARIATIONAL_EXE}" ]]; then
  echo "[ERROR] executable not found: ${MPASJEDI_VARIATIONAL_EXE}" >&2
  exit 127
fi

mpirun -np "${MPI_TASKS}" "${MPASJEDI_VARIATIONAL_EXE}" "${YAML_FILE}"
```

## What should not be inside PBS

Do not put the following responsibilities in a PBS execution wrapper unless there is a clear reason and the workflow stage is explicitly designed for it:

- workflow orchestration;
- YAML rendering;
- namelist or stream rendering;
- long chains of validation scripts;
- provenance analysis;
- report generation;
- file discovery across project trees;
- observation conversion belonging to a previous stage;
- model setup belonging to a previous stage;
- post-run diagnostic summaries that can run on the login node.

## Provenance policy

Provenance should be generated mostly by the login-node workflow. The PBS job may write simple execution metadata, such as job ID, hostname and exit code, but it should not contain a large provenance engine.

Recommended pattern:

- the workflow trace records what was prepared and which PBS job was submitted;
- the PBS stdout/stderr and application log record what happened during execution;
- post-run provenance analysis is performed on the login node by tools such as `tools/analyze_provenance.py`.

## Current 3DVar-FGAT tutorial flow

The current tutorial does not yet run the forecast/model stage. Background files are pre-staged. It also does not yet download PREPBUFR from an external source. The raw PREPBUFR file is pre-staged and converted locally.

The intended order is:

```text
login node:
  load site environment
  run smoke/preflight checks
  validate pre-staged background
  convert PREPBUFR to IODA v3
  validate converted IODA files
  render 3DVar-FGAT YAML
  validate assimilation configuration and inputs
  prepare runtime directory
  render minimal PBS job
  qsub PBS job

compute node:
  load runtime environment
  cd runtime directory
  run mpasjedi_variational.x

login node:
  inspect logs
  validate outputs
  analyze provenance
```

This separation should guide future development for the model, observation, assimilation and validation stages.
