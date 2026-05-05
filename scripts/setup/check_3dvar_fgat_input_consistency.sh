#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/check_3dvar_fgat_input_consistency.sh \
    [--sources input_sources.yaml] \
    [--staging staging.yaml] \
    [--checklist scientific_input_checklist.yaml]

Defaults:
  sources   = configs/experiments/3dvar_fgat/input_sources.example.yaml
  staging   = configs/experiments/3dvar_fgat/staging.example.yaml
  checklist = configs/experiments/3dvar_fgat/scientific_input_checklist.yaml
EOF
}

sources="${REPO_ROOT}/configs/experiments/3dvar_fgat/input_sources.example.yaml"
staging="${REPO_ROOT}/configs/experiments/3dvar_fgat/staging.example.yaml"
checklist="${REPO_ROOT}/configs/experiments/3dvar_fgat/scientific_input_checklist.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --sources)
      sources="$2"
      shift 2
      ;;
    --staging)
      staging="$2"
      shift 2
      ;;
    --checklist)
      checklist="$2"
      shift 2
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

log_info "Checking 3DVar-FGAT input consistency"
log_info "Sources:   ${sources}"
log_info "Staging:   ${staging}"
log_info "Checklist: ${checklist}"

python3 "${REPO_ROOT}/tools/check_input_consistency.py" \
  --sources "${sources}" \
  --staging "${staging}" \
  --checklist "${checklist}"
