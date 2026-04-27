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

check_command() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    log "Found command: $cmd -> $(command -v "$cmd")"
  else
    warn "Command not found: $cmd"
  fi
}

check_file() {
  local file="$1"
  if [[ -x "$file" ]]; then
    log "Executable found: $file"
  elif [[ -f "$file" ]]; then
    warn "File exists but is not executable: $file"
  else
    warn "File not found: $file"
  fi
}

check_command bash
check_command python3
check_command cylc
check_command qsub
check_command qstat
check_command "$MPI_LAUNCHER"

check_file "$MPAS_ATMOSPHERE_EXE"
check_file "$MPASJEDI_VARIATIONAL_EXE"
check_file "$MPASJEDI_HOFX_EXE"

log "Runtime check completed. Review WARN messages before running scientific experiments."
