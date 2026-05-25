#!/usr/bin/env bash
# Load the MONAN-JEDI-WORKFLOW JACI environment.
#
# This file is normally sourced:
#
#   source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
#
# It must therefore avoid leaking its positional argument into site-provided shell
# functions such as start_conda.

log() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die() {
  printf '[ERROR] %s\n' "$*" >&2
  return 1 2>/dev/null || exit 1
}

if [[ $# -ne 1 ]]; then
  die "Usage: source scripts/env/load_jaci_env.sh <site.env>"
fi

site_env="$1"
[[ -f "$site_env" ]] || die "site environment file not found: $site_env"

# shellcheck disable=SC1090
source "$site_env"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

# Compatibility for older local configs/sites/jaci/site.env files created before
# MONAN_EXTERNAL_DATA_ROOT was introduced. Keep explicit user/site values when
# already defined, otherwise derive a safe default from MONAN_JACI_WORKSPACE.
if [[ -z "${MONAN_EXTERNAL_DATA_ROOT:-}" ]]; then
  if [[ -n "${MONAN_JACI_WORKSPACE:-}" ]]; then
    export MONAN_EXTERNAL_DATA_ROOT="${MONAN_JACI_WORKSPACE}/external-inputs/3dvar_fgat"
  else
    export MONAN_EXTERNAL_DATA_ROOT="${repo_root}/external-inputs/3dvar_fgat"
  fi
  warn "MONAN_EXTERNAL_DATA_ROOT was not set; using default: ${MONAN_EXTERNAL_DATA_ROOT}"
fi

# Compatibility for older local JACI site.env files created before the workflow
# started loading the MONAN-JEDI/spack-stack-inpe runtime. Prefer explicit values
# from site.env, then common aliases, and finally the current validated JACI
# default under MONAN_JACI_WORKSPACE.
if [[ "${MONAN_LOAD_STACK:-true}" == "true" ]]; then
  export MONAN_LOAD_STACK="true"

  if [[ -z "${STACK_ROOT:-}" ]]; then
    if [[ -n "${MONAN_STACK_ROOT:-}" ]]; then
      export STACK_ROOT="${MONAN_STACK_ROOT}"
      warn "STACK_ROOT was not set; using MONAN_STACK_ROOT: ${STACK_ROOT}"
    elif [[ -n "${SPACK_STACK_ROOT:-}" ]]; then
      export STACK_ROOT="${SPACK_STACK_ROOT}"
      warn "STACK_ROOT was not set; using SPACK_STACK_ROOT: ${STACK_ROOT}"
    elif [[ -n "${MONAN_JACI_WORKSPACE:-}" ]]; then
      export STACK_ROOT="${MONAN_JACI_WORKSPACE}/work/spack-stack-inpe-overlay-20260515T181917Z/spack-stack"
      warn "STACK_ROOT was not set; using current JACI default: ${STACK_ROOT}"
    fi
  fi

  if [[ -n "${STACK_ROOT:-}" ]]; then
    export STACK_ENV_NAME="${STACK_ENV_NAME:-jaci-mpas-jedi-gcc12-craympich}"
    export STACK_MODULE_ROOT="${STACK_MODULE_ROOT:-${STACK_ROOT}/envs/${STACK_ENV_NAME}/modules}"
    export STACK_ENV_MODULE="${STACK_ENV_MODULE:-cray-mpich/8.1.31/none/none/jedi-mpas-env/1.0.0}"
    export STACK_SITE_SETUP="${STACK_SITE_SETUP:-${STACK_ROOT}/configs/sites/tier2/jaci/setup.sh}"
  else
    warn "MONAN_LOAD_STACK=true but STACK_ROOT could not be derived; stack runtime will fail unless site.env defines it"
  fi
fi

# JACI Cray/PALS runtime uses mpirun -np in the current tutorial case. Keep both
# values overridable by site.env so other platforms can use a different launcher.
export MPI_LAUNCHER="${MPI_LAUNCHER:-mpirun}"
export MPI_TASKS_FLAG="${MPI_TASKS_FLAG:--np}"

load_jaci_modules() {
  local modules_file="$1"

  if [[ -f "$modules_file" ]]; then
    log "Loading JACI modules from ${modules_file}"

    # Important: this function intentionally receives only the modules file path
    # and then clears positional parameters before sourcing modules.sh. JACI's
    # start_conda may inspect positional parameters. Without this isolation, the
    # outer site.env argument can be misinterpreted as a Conda environment path.
    set --
    # shellcheck disable=SC1090
    source "$modules_file"
  else
    warn "No modules file found at ${modules_file}; continuing without module changes"
  fi
}

modules_file="${MONAN_JACI_MODULES_FILE:-${repo_root}/configs/sites/jaci/modules.sh}"
load_jaci_modules "$modules_file" || die "failed to load JACI modules from ${modules_file}"

: "${MONAN_SITE:?MONAN_SITE is required}"
: "${MONAN_WORKFLOW_ROOT:?MONAN_WORKFLOW_ROOT is required}"
: "${MPAS_BUNDLE_BUILD:?MPAS_BUNDLE_BUILD is required}"
: "${CYLC_PLATFORM:?CYLC_PLATFORM is required}"
: "${MONAN_EXTERNAL_DATA_ROOT:?MONAN_EXTERNAL_DATA_ROOT is required}"

export PATH="${MPAS_BUNDLE_BUILD}/bin:${PATH}"
export LD_LIBRARY_PATH="${MPAS_BUNDLE_BUILD}/lib:${LD_LIBRARY_PATH:-}"

log "MONAN_SITE=${MONAN_SITE}"
log "MONAN_WORKFLOW_ROOT=${MONAN_WORKFLOW_ROOT}"
log "MONAN_DATA_ROOT=${MONAN_DATA_ROOT:-unset}"
log "MONAN_SCRATCH=${MONAN_SCRATCH:-unset}"
log "MONAN_EXTERNAL_DATA_ROOT=${MONAN_EXTERNAL_DATA_ROOT}"
log "STACK_ROOT=${STACK_ROOT:-unset}"
log "STACK_ENV_MODULE=${STACK_ENV_MODULE:-unset}"
log "MPAS_BUNDLE_BUILD=${MPAS_BUNDLE_BUILD}"
log "MPASJEDI_VARIATIONAL_EXE=${MPASJEDI_VARIATIONAL_EXE:-unset}"
log "MPI_LAUNCHER=${MPI_LAUNCHER:-unset}"
log "MPI_TASKS_FLAG=${MPI_TASKS_FLAG:-unset}"
log "CYLC_PLATFORM=${CYLC_PLATFORM}"