#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/run/render_3dvar_fgat_pbs.sh [context.yaml] [output.pbs]

Defaults:
  context.yaml = configs/experiments/3dvar_fgat/pbs_job.example.yaml
  output.pbs   = build/rendered/3dvar_fgat.pbs

This command renders a PBS job script. It does not submit the job.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

context_file="${1:-${REPO_ROOT}/configs/experiments/3dvar_fgat/pbs_job.example.yaml}"
output_file="${2:-${REPO_ROOT}/build/rendered/3dvar_fgat.pbs}"
template_file="${REPO_ROOT}/jobs/pbs/3dvar_fgat.pbs.template"
provenance_dir="${REPO_ROOT}/build/rendered/provenance"
trace_file="${provenance_dir}/3dvar_fgat_pbs.trace"
started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_epoch=$(date -u +%s)

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
result:
  status: ${status}
  exit_code: ${exit_code}
  finished_at_utc: ${finished_at_utc}
  duration_seconds: ${duration_seconds}
EOF

  exit "${exit_code}"
}
trap finalize_trace EXIT

log_info "Rendering 3DVar-FGAT PBS job"
log_info "PBS render provenance"
log_info "  started UTC   : ${started_at_utc}"
log_info "  git commit    : ${git_commit}"
log_info "  template      : ${template_file}"
log_info "  context       : ${context_file}"
log_info "  output        : ${output_file}"
log_info "  note          : this script renders only. It does not qsub."

mkdir -p "${provenance_dir}"
cat > "${trace_file}" <<EOF
started_at_utc: ${started_at_utc}
git_commit: ${git_commit}
generated_by: scripts/run/render_3dvar_fgat_pbs.sh
inputs:
  template: ${template_file}
  context: ${context_file}
command:
  executable: python3
  argv: ${REPO_ROOT}/tools/render_template.py ${template_file} --context ${context_file} --output ${output_file} --allow-env --allow-unresolved
outputs:
  pbs_script: ${output_file}
notes:
  - This script only renders PBS.
  - qsub is intentionally outside this stage.
EOF

python3 "${REPO_ROOT}/tools/render_template.py" \
  "${template_file}" \
  --context "${context_file}" \
  --output "${output_file}" \
  --allow-env \
  --allow-unresolved

log_info "Rendered PBS job written to ${output_file}"
log_info "PBS provenance trace written to ${trace_file}"
log_warn "This command only renders the job. Submit manually with qsub after inspection."
