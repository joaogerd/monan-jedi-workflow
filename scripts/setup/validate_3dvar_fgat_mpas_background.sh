#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

strict=false
background=""
layout="${REPO_ROOT}/configs/experiments/3dvar_fgat/data_layout.example.yaml"
render_context="${REPO_ROOT}/configs/experiments/3dvar_fgat/render_context.example.yaml"
data_root="${MONAN_DATA_ROOT:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      strict=true
      shift
      ;;
    --background)
      background="$2"
      shift 2
      ;;
    --layout)
      layout="$2"
      shift 2
      ;;
    --render-context)
      render_context="$2"
      shift 2
      ;;
    --data-root)
      data_root="$2"
      shift 2
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${data_root}" ]]; then
  data_root='${MONAN_DATA_ROOT}'
fi

args=(
  "${REPO_ROOT}/tools/validate_mpas_background.py"
  --layout "${layout}"
  --render-context "${render_context}"
  --data-root "${data_root}"
)

if [[ -n "${background}" ]]; then
  args+=(--background "${background}")
fi
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Validating 3DVar-FGAT MPAS background"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Missing or invalid background will fail."
else
  log_warn "Permissive mode. Missing background will be reported as warning."
fi

python3 "${args[@]}"
