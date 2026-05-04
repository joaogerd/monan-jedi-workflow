#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/check_external_input_root.sh [--allow-missing] [staging.yaml]

Defaults:
  staging.yaml = configs/experiments/3dvar_fgat/staging.example.yaml

Use --allow-missing during early setup before the external input directory exists.
EOF
}

allow_missing=false
manifest="${REPO_ROOT}/configs/experiments/3dvar_fgat/staging.example.yaml"

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
      manifest="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/check_external_input_root.py" "${manifest}")
if [[ "${allow_missing}" == true ]]; then
  args+=(--allow-missing)
fi

log_info "Checking external input root"
log_info "Manifest: ${manifest}"
if [[ "${allow_missing}" == true ]]; then
  log_warn "Missing external input root will be reported as a warning."
fi

python3 "${args[@]}"
