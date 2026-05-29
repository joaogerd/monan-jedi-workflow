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
provenance_dir="${render_dir}/provenance"
trace_file="${provenance_dir}/3dvar_fgat.trace"
started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_epoch=$(date -u +%s)

git_commit="unknown"
if command -v git >/dev/null 2>&1; then
  git_commit=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || printf 'unknown')
fi

sha256_or_missing() {
  local path="$1"
  if [[ -f "${path}" ]] && command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${path}" | awk '{print $1}'
  elif [[ -f "${path}" ]]; then
    printf 'sha256sum-not-available'
  else
    printf 'missing'
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

exists_flag() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    printf 'true'
  else
    printf 'false'
  fi
}

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
artifact_checksums:
  template:
    path: ${template_file}
    exists: $(exists_flag "${template_file}")
    size_bytes: $(file_size_bytes "${template_file}")
    sha256: $(sha256_or_missing "${template_file}")
  context:
    path: ${context_file}
    exists: $(exists_flag "${context_file}")
    size_bytes: $(file_size_bytes "${context_file}")
    sha256: $(sha256_or_missing "${context_file}")
  observer_manifest:
    path: ${observer_manifest}
    exists: $(exists_flag "${observer_manifest}")
    size_bytes: $(file_size_bytes "${observer_manifest}")
    sha256: $(sha256_or_missing "${observer_manifest}")
  observers_yaml:
    path: ${observers_file}
    exists: $(exists_flag "${observers_file}")
    size_bytes: $(file_size_bytes "${observers_file}")
    sha256: $(sha256_or_missing "${observers_file}")
  combined_context:
    path: ${combined_context}
    exists: $(exists_flag "${combined_context}")
    size_bytes: $(file_size_bytes "${combined_context}")
    sha256: $(sha256_or_missing "${combined_context}")
  rendered_yaml:
    path: ${output_file}
    exists: $(exists_flag "${output_file}")
    size_bytes: $(file_size_bytes "${output_file}")
    sha256: $(sha256_or_missing "${output_file}")
result:
  status: ${status}
  exit_code: ${exit_code}
  finished_at_utc: ${finished_at_utc}
  duration_seconds: ${duration_seconds}
EOF

  exit "${exit_code}"
}
trap finalize_trace EXIT

log_info "3DVar-FGAT render provenance"
log_info "  started UTC   : ${started_at_utc}"
log_info "  git commit    : ${git_commit}"
log_info "  script        : scripts/run/render_3dvar_fgat.sh"
log_info "  template      : ${template_file}"
log_info "  context       : ${context_file}"
log_info "  observers     : ${observer_manifest}"
log_info "  observers out : ${observers_file}"
log_info "  combined ctx  : ${combined_context}"
log_info "  final YAML    : ${output_file}"

mkdir -p "${provenance_dir}"
cat > "${trace_file}" <<EOF
started_at_utc: ${started_at_utc}
git_commit: ${git_commit}
generated_by: scripts/run/render_3dvar_fgat.sh
inputs:
  template: ${template_file}
  context: ${context_file}
  observer_manifest: ${observer_manifest}
commands:
  render_observers: python3 ${REPO_ROOT}/tools/render_observers.py ${observer_manifest} --context ${context_file} --output ${observers_file} --allow-env --allow-unresolved
  render_template: python3 ${REPO_ROOT}/tools/render_template.py ${template_file} --context ${combined_context} --output ${output_file} --allow-env --allow-unresolved
intermediate_outputs:
  observers_yaml: ${observers_file}
  combined_context: ${combined_context}
outputs:
  jedi_yaml: ${output_file}
notes:
  - This trace records artifact provenance only.
  - The rendered YAML is a structural smoke output unless validated by the runtime workflow.
EOF

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
log_info "Rendered combined context written to ${combined_context}"
log_info "Rendered file written to ${output_file}"
log_info "Provenance trace written to ${trace_file}"
log_warn "This rendered YAML is a structural smoke output, not a validated scientific run configuration."
