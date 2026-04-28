#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/run/run_3dvar_fgat_variational.sh [--execute] [--strict] [config.yaml]

Defaults:
  config.yaml = configs/experiments/3dvar_fgat/run_command.example.yaml

Default mode is dry-run. Use --execute to run mpasjedi_variational.x.
EOF
}

execute=false
strict=false
config="${REPO_ROOT}/configs/experiments/3dvar_fgat/run_command.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --execute)
      execute=true
      shift
      ;;
    --strict)
      strict=true
      shift
      ;;
    *)
      config="$1"
      shift
      ;;
  esac
done

command_file="${REPO_ROOT}/build/rendered/mpasjedi_variational.command"
args=("${REPO_ROOT}/tools/run_variational.py" "${config}" --command-file "${command_file}")

if [[ "${execute}" == true ]]; then
  args+=(--execute)
fi
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Preparing JEDI-MPAS variational command"
log_info "Config: ${config}"
if [[ "${execute}" != true ]]; then
  log_warn "Dry-run mode. Use --execute only inside a validated runtime/PBS environment."
fi

python3 "${args[@]}"
