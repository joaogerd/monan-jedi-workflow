#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/setup/check_mpas_jedi_build.sh [--strict] [mpas_jedi_build.yaml]

Defaults:
  mpas_jedi_build.yaml = configs/sites/jaci/mpas_jedi_build.example.yaml

Default mode reports placeholder/missing paths as warnings.
Use --strict only after MPAS_BUNDLE_BUILD and executable variables point to a real build.
EOF
}

strict=false
manifest="${REPO_ROOT}/configs/sites/jaci/mpas_jedi_build.example.yaml"

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
    *)
      manifest="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/check_mpas_jedi_build.py" "${manifest}")
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Checking MPAS-JEDI build"
log_info "Manifest: ${manifest}"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Missing required executables will fail."
fi

python3 "${args[@]}"
