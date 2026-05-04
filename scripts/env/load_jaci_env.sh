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
log "MPAS_BUNDLE_BUILD=${MPAS_BUNDLE_BUILD}"
log "MPASJEDI_VARIATIONAL_EXE=${MPASJEDI_VARIATIONAL_EXE:-unset}"
log "MPI_LAUNCHER=${MPI_LAUNCHER:-unset}"
log "CYLC_PLATFORM=${CYLC_PLATFORM}"
