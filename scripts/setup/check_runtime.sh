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

check_required_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    warn "Required variable is not set: ${name}"
  else
    log "${name}=${!name}"
  fi
}

check_command() {
  local cmd="$1"
  if [[ -z "$cmd" ]]; then
    warn "Empty command name"
    return
  fi
  if command -v "$cmd" >/dev/null 2>&1; then
    log "Found command: $cmd -> $(command -v "$cmd")"
  else
    warn "Command not found: $cmd"
  fi
}

check_file() {
  local file="$1"
  if [[ "$file" == *'$'* ]]; then
    warn "Path still contains unresolved variable: $file"
  elif [[ -x "$file" ]]; then
    log "Executable found: $file"
  elif [[ -f "$file" ]]; then
    warn "File exists but is not executable: $file"
  else
    warn "File not found: $file"
  fi
}

check_dir() {
  local dir="$1"
  if [[ "$dir" == *'$'* ]]; then
    warn "Directory path still contains unresolved variable: $dir"
  elif [[ -d "$dir" ]]; then
    log "Directory found: $dir"
  else
    warn "Directory not found: $dir"
  fi
}

log "Checking required JACI/MONAN variables"
for var in \
  MONAN_SITE \
  MONAN_PROJECT \
  MONAN_QUEUE \
  MONAN_WORKFLOW_ROOT \
  MONAN_WORK_ROOT \
  MONAN_SCRATCH \
  MONAN_DATA_ROOT \
  MPAS_BUNDLE_BUILD \
  MPAS_ATMOSPHERE_EXE \
  MPASJEDI_VARIATIONAL_EXE \
  MPASJEDI_HOFX_EXE \
  MPI_LAUNCHER \
  CYLC_PLATFORM; do
  check_required_var "$var"
done

log "Checking required commands"
check_command bash
check_command python3
check_command cylc
check_command qsub
check_command qstat
check_command "${MPI_LAUNCHER:-}"

log "Checking MPAS/JEDI executables"
check_file "${MPAS_ATMOSPHERE_EXE:-}"
check_file "${MPASJEDI_VARIATIONAL_EXE:-}"
check_file "${MPASJEDI_HOFX_EXE:-}"

log "Checking important directories"
check_dir "${MONAN_WORKFLOW_ROOT:-}"
check_dir "${MONAN_WORK_ROOT:-}"
check_dir "${MONAN_SCRATCH:-}"
check_dir "${MONAN_DATA_ROOT:-}"
check_dir "${MONAN_BACKGROUND_ROOT:-}"
check_dir "${MONAN_IODA_ROOT:-}"
check_dir "${MONAN_COVARIANCE_ROOT:-}"
check_dir "${MONAN_GRAPH_ROOT:-}"
check_dir "${MONAN_STATIC_ROOT:-}"

log "Runtime check completed. Review WARN messages before running scientific experiments."
