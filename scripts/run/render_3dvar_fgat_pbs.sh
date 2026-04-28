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

log_info "Rendering 3DVar-FGAT PBS job"
log_info "Template: ${template_file}"
log_info "Context : ${context_file}"
log_info "Output  : ${output_file}"

python3 "${REPO_ROOT}/tools/render_template.py" \
  "${template_file}" \
  --context "${context_file}" \
  --output "${output_file}" \
  --allow-env \
  --allow-unresolved

log_info "Rendered PBS job written to ${output_file}"
log_warn "This command only renders the job. Submit manually with qsub after inspection."
