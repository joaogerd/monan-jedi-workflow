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
observer_manifest="${REPO_ROOT}/configs/experiments/3dvar_fgat/observers.yaml"
render_dir="${REPO_ROOT}/build/rendered"
observers_file="${render_dir}/observers.yaml"
combined_context="${render_dir}/render_context.with_observers.yaml"

log_info "Rendering 3DVar-FGAT observers"
python3 "${REPO_ROOT}/tools/render_observers.py" \
  "${observer_manifest}" \
  --context "${context_file}" \
  --output "${observers_file}" \
  --allow-env \
  --allow-unresolved

log_info "Preparing combined render context"
python3 - "${context_file}" "${observers_file}" "${combined_context}" <<'PY'
from pathlib import Path
import sys
import yaml

context_path = Path(sys.argv[1])
observers_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])

context = yaml.safe_load(context_path.read_text(encoding="utf-8")) or {}
observers_text = observers_path.read_text(encoding="utf-8")
context.setdefault("jedi", {})["observers"] = "\n".join(
    "    " + line if line else line
    for line in observers_text.rstrip().splitlines()
)
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(yaml.safe_dump(context, sort_keys=False), encoding="utf-8")
PY

log_info "Rendering 3DVar-FGAT template"
log_info "Template: ${template_file}"
log_info "Context : ${combined_context}"
log_info "Output  : ${output_file}"

python3 "${REPO_ROOT}/tools/render_template.py" \
  "${template_file}" \
  --context "${combined_context}" \
  --output "${output_file}" \
  --allow-env \
  --allow-unresolved

log_info "Rendered observers written to ${observers_file}"
log_info "Rendered file written to ${output_file}"
log_warn "This rendered YAML is a structural smoke output, not a validated scientific run configuration."
