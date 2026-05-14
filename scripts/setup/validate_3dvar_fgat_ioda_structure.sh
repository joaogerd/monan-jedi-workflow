#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/validate_3dvar_fgat_ioda_structure.sh [--strict]

Optional arguments:
  --inventory FILE   IODA inventory YAML
  --manifest FILE    observer manifest YAML
  --data-root DIR    staged data root

Defaults:
  inventory = configs/experiments/3dvar_fgat/ioda_inventory.example.yaml
  manifest  = configs/experiments/3dvar_fgat/observers.yaml
  data-root = ${MONAN_DATA_ROOT}

Default mode is permissive and reports missing/incomplete IODA files as warnings.
Use --strict only after real IODA files have been staged.
EOF
}

strict=false
inventory="${REPO_ROOT}/configs/experiments/3dvar_fgat/ioda_inventory.example.yaml"
manifest="${REPO_ROOT}/configs/experiments/3dvar_fgat/observers.yaml"
data_root="${MONAN_DATA_ROOT:-}"

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
    --inventory)
      inventory="$2"
      shift 2
      ;;
    --manifest)
      manifest="$2"
      shift 2
      ;;
    --data-root)
      data_root="$2"
      shift 2
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

args=(
  "${REPO_ROOT}/tools/validate_ioda_structure.py"
  --inventory "${inventory}"
  --manifest "${manifest}"
  --data-root "${data_root:-\${MONAN_DATA_ROOT}}"
)
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Validating basic 3DVar-FGAT IODA structure"
log_info "Inventory: ${inventory}"
log_info "Manifest : ${manifest}"
log_info "Data root: ${data_root:-\${MONAN_DATA_ROOT}}"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Missing or incomplete IODA files will fail."
else
  log_warn "Permissive mode. Missing IODA files will be reported as warnings."
fi

python3 "${args[@]}"
