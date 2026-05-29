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

provenance_dir="${REPO_ROOT}/build/rendered/provenance"
trace_file="${provenance_dir}/variational.trace"

git_commit="unknown"
if command -v git >/dev/null 2>&1; then
  git_commit=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || printf 'unknown')
fi

timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)

log_info "Preparing JEDI-MPAS variational command"
log_info "Variational provenance"
log_info "  timestamp UTC : ${timestamp_utc}"
log_info "  git commit    : ${git_commit}"
log_info "  config        : ${config}"
log_info "  execute mode  : ${execute}"
log_info "  strict mode   : ${strict}"
log_info "  command file  : ${command_file}"

if [[ "${execute}" != true ]]; then
  log_warn "Dry-run mode. Use --execute only inside a validated runtime/PBS environment."
fi

python3 "${args[@]}"

mkdir -p "${provenance_dir}"
cat > "${trace_file}" <<EOF
timestamp_utc: ${timestamp_utc}
git_commit: ${git_commit}
generated_by: scripts/run/run_3dvar_fgat_variational.sh
inputs:
  run_config: ${config}
execution:
  execute_mode: ${execute}
  strict_mode: ${strict}
outputs:
  command_file: ${command_file}
notes:
  - This stage creates the command file.
  - Actual execution only happens when execute_mode=true.
EOF

log_info "Variational provenance trace written to ${trace_file}"
