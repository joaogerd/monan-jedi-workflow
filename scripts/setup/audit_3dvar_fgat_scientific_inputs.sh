#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/audit_3dvar_fgat_scientific_inputs.sh [--strict] [checklist.yaml]

Defaults:
  checklist.yaml = configs/experiments/3dvar_fgat/scientific_input_checklist.yaml

Default mode reports checklist status without failing on pending scientific inputs.
Use --strict only after required files have been staged and validated.
EOF
}

strict=false
checklist="${REPO_ROOT}/configs/experiments/3dvar_fgat/scientific_input_checklist.yaml"

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
      checklist="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/audit_scientific_inputs.py" "${checklist}")
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Auditing 3DVar-FGAT scientific input checklist"
log_info "Checklist: ${checklist}"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Pending required inputs will fail."
fi

python3 "${args[@]}"
