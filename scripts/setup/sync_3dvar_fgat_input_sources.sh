#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/sync_3dvar_fgat_input_sources.sh [--dry-run] [--copy] [input_sources.yaml]

Defaults:
  input_sources.yaml = configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml

Default action is to create symbolic links from each source_path into
MONAN_EXTERNAL_DATA_ROOT using the external_target declared in the registry.

This conservative version never replaces existing targets.
EOF
}

dry_run=false
copy_mode=false
registry="${REPO_ROOT}/configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --copy)
      copy_mode=true
      shift
      ;;
    *)
      registry="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/sync_input_sources.py" "${registry}")
if [[ "${dry_run}" == true ]]; then
  args+=(--dry-run)
fi
if [[ "${copy_mode}" == true ]]; then
  args+=(--copy)
fi

log_info "Synchronizing 3DVar-FGAT input sources into external tree"
log_info "Registry: ${registry}"
if [[ "${dry_run}" == true ]]; then
  log_warn "Dry-run mode. No files will be changed."
fi
if [[ "${copy_mode}" == true ]]; then
  log_info "Mode: copy"
else
  log_info "Mode: link"
fi

python3 "${args[@]}"
