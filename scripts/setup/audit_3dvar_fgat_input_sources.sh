#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/audit_3dvar_fgat_input_sources.sh [--strict] [input_sources.yaml]

Defaults:
  input_sources.yaml = configs/experiments/3dvar_fgat/input_sources.example.yaml

Default mode reports empty or pending sources without failing.
Use --strict only after real source_path values and MPAS-JEDI executable paths are configured.
EOF
}

strict=false
registry="${REPO_ROOT}/configs/experiments/3dvar_fgat/input_sources.example.yaml"

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
      registry="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/audit_input_sources.py" "${registry}")
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Auditing 3DVar-FGAT real input source registry"
log_info "Registry: ${registry}"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Missing required sources will fail."
fi

python3 "${args[@]}"
