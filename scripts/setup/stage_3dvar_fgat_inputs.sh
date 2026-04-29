#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/stage_3dvar_fgat_inputs.sh [--dry-run] [--copy|--link] [--force] [manifest.yaml]

Defaults:
  manifest.yaml = configs/experiments/3dvar_fgat/staging.example.yaml

Default action is defined by the manifest. Use --dry-run before staging real files.
EOF
}

dry_run=false
copy_mode=false
link_mode=false
force=false
manifest="${REPO_ROOT}/configs/experiments/3dvar_fgat/staging.example.yaml"

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
    --link)
      link_mode=true
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

args=("${REPO_ROOT}/tools/stage_inputs.py" "${manifest}")
if [[ "${dry_run}" == true ]]; then
  args+=(--dry-run)
fi
if [[ "${copy_mode}" == true ]]; then
  args+=(--copy)
fi
if [[ "${link_mode}" == true ]]; then
  args+=(--link)
fi
if [[ "${force}" == true ]]; then
  args+=(--force)
fi

log_info "Staging 3DVar-FGAT input files"
log_info "Manifest: ${manifest}"
if [[ "${dry_run}" == true ]]; then
  log_warn "Dry-run mode. No files will be linked or copied."
fi

python3 "${args[@]}"
