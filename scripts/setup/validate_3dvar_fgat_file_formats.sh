#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/validate_3dvar_fgat_file_formats.sh [--strict] [data_layout.yaml]

Defaults:
  data_layout.yaml = configs/experiments/3dvar_fgat/data_layout.example.yaml

Default mode is permissive and reports missing or invalid files as warnings.
Use --strict only after real files have been staged under MONAN_DATA_ROOT.
EOF
}

strict=false
layout="${REPO_ROOT}/configs/experiments/3dvar_fgat/data_layout.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --strict)
      strict=true
      shift
      ;;
    *)
      layout="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/validate_file_formats.py" "${layout}")
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Validating basic 3DVar-FGAT staged file formats"
log_info "Layout: ${layout}"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Missing or invalid required files will fail."
else
  log_warn "Permissive mode. Missing files will be reported as warnings."
fi

python3 "${args[@]}"
