#!/usr/bin/env bash
set -euo pipefail

log() { printf '[INFO] %s\n' "$*"; }
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

modules_file="${repo_root}/configs/sites/jaci/modules.sh"
if [[ -f "$modules_file" ]]; then
  log "Loading JACI modules from ${modules_file}"
  # shellcheck disable=SC1090
  source "$modules_file"
else
  log "No modules file found at ${modules_file}; continuing without module changes"
fi

export PATH="${MPAS_BUNDLE_BUILD}/bin:${PATH}"
export LD_LIBRARY_PATH="${MPAS_BUNDLE_BUILD}/lib:${LD_LIBRARY_PATH:-}"

log "MONAN_SITE=${MONAN_SITE}"
log "MPAS_BUNDLE_BUILD=${MPAS_BUNDLE_BUILD}"
log "CYLC_PLATFORM=${CYLC_PLATFORM}"
