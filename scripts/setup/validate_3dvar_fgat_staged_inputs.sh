#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/validate_3dvar_fgat_staged_inputs.sh [--allow-missing] [layout.yaml]

Defaults:
  layout.yaml = configs/experiments/3dvar_fgat/data_layout.example.yaml

Default behavior fails when expected files are missing.
Use --allow-missing during early setup stages.
EOF
}

allow_missing=false
layout="${REPO_ROOT}/configs/experiments/3dvar_fgat/data_layout.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --allow-missing)
      allow_missing=true
      shift
      ;;
    *)
      layout="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/validate_staged_inputs.py" "${layout}")
if [[ "${allow_missing}" == true ]]; then
  args+=(--allow-missing)
fi

log_info "Validating staged 3DVar-FGAT input files"
log_info "Layout: ${layout}"
if [[ "${allow_missing}" == true ]]; then
  log_warn "Missing files will be reported as warnings."
fi

python3 "${args[@]}"
