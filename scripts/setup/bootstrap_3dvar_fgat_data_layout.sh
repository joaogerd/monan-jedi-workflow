#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/bootstrap_3dvar_fgat_data_layout.sh [--dry-run] [--check-files] [layout.yaml]

Defaults:
  layout.yaml = configs/experiments/3dvar_fgat/data_layout.example.yaml

By default this creates expected directories under ${MONAN_DATA_ROOT}.
Use --dry-run to only print actions.
Use --check-files to fail if expected scientific files are missing.
EOF
}

dry_run=false
check_files=false
layout="${REPO_ROOT}/configs/experiments/3dvar_fgat/data_layout.example.yaml"

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
    --check-files)
      check_files=true
      shift
      ;;
    *)
      layout="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/bootstrap_data_layout.py" "${layout}")
if [[ "${dry_run}" == true ]]; then
  args+=(--dry-run)
fi
if [[ "${check_files}" == true ]]; then
  args+=(--check-files)
fi

log_info "Bootstrapping 3DVar-FGAT data layout"
log_info "Layout: ${layout}"
if [[ "${dry_run}" == true ]]; then
  log_warn "Dry-run mode. No directories will be created."
fi

python3 "${args[@]}"
