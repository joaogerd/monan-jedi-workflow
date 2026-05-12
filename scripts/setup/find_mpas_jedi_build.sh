#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/find_mpas_jedi_build.sh [--strict] [--max-depth N] [search_root ...]

Examples:
  scripts/setup/find_mpas_jedi_build.sh
  scripts/setup/find_mpas_jedi_build.sh --max-depth 6 ${MONAN_JACI_WORKSPACE}/projects
  scripts/setup/find_mpas_jedi_build.sh --strict ${MONAN_JACI_WORKSPACE}/projects/jedi

Default mode does not fail when no candidates are found.
EOF
}

strict=false
max_depth=5
roots=()

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
    --max-depth)
      max_depth="$2"
      shift 2
      ;;
    *)
      roots+=("$1")
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/find_mpas_jedi_build.py" --max-depth "${max_depth}")
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi
if [[ ${#roots[@]} -gt 0 ]]; then
  args+=("${roots[@]}")
fi

log_info "Finding MPAS-JEDI build candidates"
log_info "Max depth: ${max_depth}"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Missing 3DVar-capable build will fail."
fi

python3 "${args[@]}"
