#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/run/render_3dvar_fgat.sh [context.yaml] [output.yaml]

Defaults:
  context.yaml = configs/experiments/3dvar_fgat/render_context.example.yaml
  output.yaml  = build/rendered/3dvar_fgat.yaml

This command renders the MONAN 3DVar-FGAT JEDI application template. It does not run MPAS-JEDI.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

context_file="${1:-${REPO_ROOT}/configs/experiments/3dvar_fgat/render_context.example.yaml}"
output_file="${2:-${REPO_ROOT}/build/rendered/3dvar_fgat.yaml}"
template_file="${REPO_ROOT}/configs/jedi/applications/3dvar_fgat.yaml"

log_info "Rendering 3DVar-FGAT template"
log_info "Template: ${template_file}"
log_info "Context : ${context_file}"
log_info "Output  : ${output_file}"

python3 "${REPO_ROOT}/tools/render_template.py" \
  "${template_file}" \
  --context "${context_file}" \
  --output "${output_file}" \
  --allow-env \
  --allow-unresolved

log_info "Rendered file written to ${output_file}"
log_warn "This rendered YAML is a structural smoke output, not a validated scientific run configuration."
