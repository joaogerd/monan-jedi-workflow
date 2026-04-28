#!/usr/bin/env bash
set -euo pipefail

log() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

if [[ $# -ne 1 ]]; then
  die "Usage: $0 <site.env>"
fi

site_env="$1"
[[ -f "$site_env" ]] || die "site environment file not found: $site_env"

# shellcheck disable=SC1090
source "$site_env"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"

modules_file="${MONAN_JACI_MODULES_FILE:-${repo_root}/configs/sites/jaci/modules.sh}"
if [[ -f "$modules_file" ]]; then
  log "Loading JACI modules from ${modules_file}"
  # shellcheck disable=SC1090
  source "$modules_file"
else
  warn "No modules file found at ${modules_file}; continuing without module changes"
fi

: "${MONAN_SITE:?MONAN_SITE is required}"
: "${MONAN_WORKFLOW_ROOT:?MONAN_WORKFLOW_ROOT is required}"
: "${MPAS_BUNDLE_BUILD:?MPAS_BUNDLE_BUILD is required}"
: "${CYLC_PLATFORM:?CYLC_PLATFORM is required}"

export PATH="${MPAS_BUNDLE_BUILD}/bin:${PATH}"
export LD_LIBRARY_PATH="${MPAS_BUNDLE_BUILD}/lib:${LD_LIBRARY_PATH:-}"

log "MONAN_SITE=${MONAN_SITE}"
log "MONAN_WORKFLOW_ROOT=${MONAN_WORKFLOW_ROOT}"
log "MONAN_DATA_ROOT=${MONAN_DATA_ROOT:-unset}"
log "MONAN_SCRATCH=${MONAN_SCRATCH:-unset}"
log "MPAS_BUNDLE_BUILD=${MPAS_BUNDLE_BUILD}"
log "MPASJEDI_VARIATIONAL_EXE=${MPASJEDI_VARIATIONAL_EXE:-unset}"
log "MPI_LAUNCHER=${MPI_LAUNCHER:-unset}"
log "CYLC_PLATFORM=${CYLC_PLATFORM}"
