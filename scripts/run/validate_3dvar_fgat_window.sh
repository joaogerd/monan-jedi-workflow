#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

strict=false
experiment="${REPO_ROOT}/configs/experiments/3dvar_fgat/experiment.yaml"
render_context="${REPO_ROOT}/configs/experiments/3dvar_fgat/render_context.example.yaml"
jedi_yaml="${REPO_ROOT}/build/rendered/3dvar_fgat.yaml"
ioda_inventory="${REPO_ROOT}/configs/experiments/3dvar_fgat/ioda_inventory.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      strict=true
      shift
      ;;
    --experiment)
      experiment="$2"
      shift 2
      ;;
    --render-context)
      render_context="$2"
      shift 2
      ;;
    --jedi-yaml)
      jedi_yaml="$2"
      shift 2
      ;;
    --ioda-inventory)
      ioda_inventory="$2"
      shift 2
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

args=(
  "${REPO_ROOT}/tools/validate_fgat_window.py"
  --experiment "${experiment}"
  --render-context "${render_context}"
  --jedi-yaml "${jedi_yaml}"
  --ioda-inventory "${ioda_inventory}"
)
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Validating 3DVar-FGAT window structure"
python3 "${args[@]}"
