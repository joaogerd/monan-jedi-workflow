#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/create_3dvar_fgat_external_tree.sh [--dry-run]

Creates the expected MONAN_EXTERNAL_DATA_ROOT directory tree for the first
MONAN/JEDI 3DVar-FGAT case.

Required environment:
  MONAN_EXTERNAL_DATA_ROOT
EOF
}

dry_run=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

: "${MONAN_EXTERNAL_DATA_ROOT:?MONAN_EXTERNAL_DATA_ROOT is required. Source configs/sites/jaci/site.env first.}"

paths=(
  "${MONAN_EXTERNAL_DATA_ROOT}/background/2024081500"
  "${MONAN_EXTERNAL_DATA_ROOT}/observations/ioda/2024081500"
  "${MONAN_EXTERNAL_DATA_ROOT}/covariance"
  "${MONAN_EXTERNAL_DATA_ROOT}/graph"
  "${MONAN_EXTERNAL_DATA_ROOT}/static"
)

log_info "Creating 3DVar-FGAT external input tree"
log_info "External root: ${MONAN_EXTERNAL_DATA_ROOT}"
if [[ "${dry_run}" == true ]]; then
  log_warn "Dry-run mode. No directories will be created."
fi

for path in "${paths[@]}"; do
  if [[ "${dry_run}" == true ]]; then
    echo "[DRY-RUN] mkdir -p ${path}"
  else
    mkdir -p "${path}"
    log_info "Directory ready: ${path}"
  fi
done

log_info "Expected first-case external files:"
cat <<EOF
  ${MONAN_EXTERNAL_DATA_ROOT}/background/2024081500/mpasout.2024-08-15_00.00.00.nc
  ${MONAN_EXTERNAL_DATA_ROOT}/observations/ioda/2024081500/aircraft_obs_2024081500.h5
  ${MONAN_EXTERNAL_DATA_ROOT}/observations/ioda/2024081500/sondes_obs_2024081500.h5
  ${MONAN_EXTERNAL_DATA_ROOT}/observations/ioda/2024081500/sfc_obs_2024081500.h5
  ${MONAN_EXTERNAL_DATA_ROOT}/covariance/mpas.stddev.nc
  ${MONAN_EXTERNAL_DATA_ROOT}/graph/graph.info.part.0128
  ${MONAN_EXTERNAL_DATA_ROOT}/static/x1.static.nc
EOF

log_info "External input tree preparation completed"
