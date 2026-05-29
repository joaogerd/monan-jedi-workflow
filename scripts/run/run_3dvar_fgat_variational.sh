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
started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_epoch=$(date -u +%s)

experiment_name="jaci_3dvar_fgat_tutorial_2018041500"
cycle="2018041500"
runtime_dir="${REPO_ROOT}/build/runtime/${experiment_name}/${cycle}"
runtime_log_dir="${runtime_dir}/logs"
runtime_analysis_dir="${runtime_dir}/analysis"
runtime_feedback_dir="${runtime_dir}/feedback"
variational_log="${runtime_log_dir}/mpasjedi_variational.log"
rendered_yaml="${REPO_ROOT}/build/rendered/3dvar_fgat.yaml"
scratch_root="${MONAN_SCRATCH:-${REPO_ROOT}/build/scratch}"
scratch_experiment_dir="${scratch_root}/${experiment_name}"
scratch_analysis_dir="${scratch_experiment_dir}/analysis"
scratch_feedback_dir="${scratch_experiment_dir}/feedback"

exists_flag() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    printf 'true'
  else
    printf 'false'
  fi
}

dir_count() {
  local path="$1"
  if [[ -d "${path}" ]]; then
    find "${path}" -mindepth 1 -maxdepth 1 2>/dev/null | wc -l | tr -d ' '
  else
    printf '0'
  fi
}

file_size_bytes() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    wc -c < "${path}" | tr -d ' '
  else
    printf '0'
  fi
}

git_commit="unknown"
if command -v git >/dev/null 2>&1; then
  git_commit=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || printf 'unknown')
fi

finalize_trace() {
  local exit_code=$?
  local finished_at_utc
  local finished_epoch
  local duration_seconds
  local status

  finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  finished_epoch=$(date -u +%s)
  duration_seconds=$((finished_epoch - started_epoch))

  if [[ ${exit_code} -eq 0 ]]; then
    status="completed"
  else
    status="failed"
  fi

  mkdir -p "${provenance_dir}"
  cat >> "${trace_file}" <<EOF
observed_outputs:
  command_file:
    path: ${command_file}
    exists: $(exists_flag "${command_file}")
    size_bytes: $(file_size_bytes "${command_file}")
  variational_log:
    path: ${variational_log}
    exists: $(exists_flag "${variational_log}")
    size_bytes: $(file_size_bytes "${variational_log}")
  runtime_analysis_dir:
    path: ${runtime_analysis_dir}
    exists: $(exists_flag "${runtime_analysis_dir}")
    entries: $(dir_count "${runtime_analysis_dir}")
  runtime_feedback_dir:
    path: ${runtime_feedback_dir}
    exists: $(exists_flag "${runtime_feedback_dir}")
    entries: $(dir_count "${runtime_feedback_dir}")
  scratch_analysis_dir:
    path: ${scratch_analysis_dir}
    exists: $(exists_flag "${scratch_analysis_dir}")
    entries: $(dir_count "${scratch_analysis_dir}")
  scratch_feedback_dir:
    path: ${scratch_feedback_dir}
    exists: $(exists_flag "${scratch_feedback_dir}")
    entries: $(dir_count "${scratch_feedback_dir}")
result:
  status: ${status}
  exit_code: ${exit_code}
  finished_at_utc: ${finished_at_utc}
  duration_seconds: ${duration_seconds}
EOF

  exit "${exit_code}"
}
trap finalize_trace EXIT

log_info "Preparing JEDI-MPAS variational command"
log_info "Variational provenance"
log_info "  started UTC   : ${started_at_utc}"
log_info "  git commit    : ${git_commit}"
log_info "  config        : ${config}"
log_info "  execute mode  : ${execute}"
log_info "  strict mode   : ${strict}"
log_info "  command file  : ${command_file}"
log_info "  runtime dir   : ${runtime_dir}"
log_info "  JEDI log      : ${variational_log}"

if [[ "${execute}" != true ]]; then
  log_warn "Dry-run mode. Use --execute only inside a validated runtime/PBS environment."
fi

mkdir -p "${provenance_dir}"
cat > "${trace_file}" <<EOF
started_at_utc: ${started_at_utc}
git_commit: ${git_commit}
generated_by: scripts/run/run_3dvar_fgat_variational.sh
inputs:
  run_config: ${config}
  rendered_yaml: ${rendered_yaml}
  runtime_dir: ${runtime_dir}
execution:
  execute_mode: ${execute}
  strict_mode: ${strict}
command:
  executable: python3
  argv: ${args[*]}
expected_outputs:
  command_file: ${command_file}
  variational_log: ${variational_log}
  runtime_analysis_dir: ${runtime_analysis_dir}
  runtime_feedback_dir: ${runtime_feedback_dir}
  scratch_analysis_dir: ${scratch_analysis_dir}
  scratch_feedback_dir: ${scratch_feedback_dir}
notes:
  - This stage always creates or refreshes the command file.
  - Actual JEDI execution only happens when execute_mode=true.
  - observed_outputs is written at script exit and records which expected outputs actually exist.
EOF

python3 "${args[@]}"

log_info "Variational provenance trace written to ${trace_file}"
