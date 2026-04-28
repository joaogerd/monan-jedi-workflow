#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/run/prepare_3dvar_fgat_runtime.sh [--strict] [--copy] [--force] [manifest.yaml]

Defaults:
  manifest.yaml = configs/experiments/3dvar_fgat/runtime_manifest.example.yaml

Default mode is dry-run. Use --strict to create links/copies and require mandatory files.
EOF
}

dry_run=true
copy_mode=false
force=false
manifest="${REPO_ROOT}/configs/experiments/3dvar_fgat/runtime_manifest.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --strict)
      dry_run=false
      shift
      ;;
    --copy)
      copy_mode=true
      shift
      ;;
    --force)
      force=true
      shift
      ;;
    *)
      manifest="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/prepare_runtime.py" "${manifest}")
if [[ "${dry_run}" == true ]]; then
  args+=(--dry-run)
fi
if [[ "${copy_mode}" == true ]]; then
  args+=(--copy)
fi
if [[ "${force}" == true ]]; then
  args+=(--force)
fi

log_info "Preparing 3DVar-FGAT runtime"
log_info "Manifest: ${manifest}"
if [[ "${dry_run}" == true ]]; then
  log_warn "Running in dry-run mode. Use --strict to create links/copies."
fi

python3 "${args[@]}"
