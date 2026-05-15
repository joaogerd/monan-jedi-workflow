#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

strict=false
render_context="${REPO_ROOT}/configs/experiments/3dvar_fgat/render_context.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      strict=true
      shift
      ;;
    --render-context)
      render_context="$2"
      shift 2
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

args=("${REPO_ROOT}/tools/validate_saber_inputs.py" --render-context "${render_context}")
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Validating 3DVar-FGAT SABER/BUMP inputs"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Missing SABER inputs will fail."
else
  log_warn "Permissive mode. Missing SABER inputs will be reported as warnings."
fi

python3 "${args[@]}"
