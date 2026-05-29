#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/run/prepare_3dvar_fgat_runtime.sh [--strict] [--copy] [--force] [manifest.yaml]

Defaults:
  manifest.yaml = configs/experiments/3dvar_fgat/runtime_manifest.example.yaml

Default mode is dry-run. Use --strict to create links/copies and require mandatory files.
EOF
}

dry_run=true
copy_mode=false
force=false
manifest="${REPO_ROOT}/configs/experiments/3dvar_fgat/runtime_manifest.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --strict)
      dry_run=false
      shift
      ;;
    --copy)
      copy_mode=true
      shift
      ;;
    --force)
      force=true
      shift
      ;;
    *)
      manifest="$1"
      shift
      ;;
  esac
done

args=("${REPO_ROOT}/tools/prepare_runtime.py" "${manifest}")
if [[ "${dry_run}" == true ]]; then
  args+=(--dry-run)
fi
if [[ "${copy_mode}" == true ]]; then
  args+=(--copy)
fi
if [[ "${force}" == true ]]; then
  args+=(--force)
fi

render_dir="${REPO_ROOT}/build/rendered"
provenance_dir="${render_dir}/provenance"
trace_file="${provenance_dir}/runtime.trace"

git_commit="unknown"
if command -v git >/dev/null 2>&1; then
  git_commit=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || printf 'unknown')
fi

timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)

log_info "Preparing 3DVar-FGAT runtime"
log_info "Runtime preparation provenance"
log_info "  timestamp UTC : ${timestamp_utc}"
log_info "  git commit    : ${git_commit}"
log_info "  script        : scripts/run/prepare_3dvar_fgat_runtime.sh"
log_info "  manifest      : ${manifest}"
log_info "  mode dry-run  : ${dry_run}"
log_info "  mode copy     : ${copy_mode}"
log_info "  mode force    : ${force}"
log_info "  note          : this script prepares runtime files; it does not render PBS"
if [[ "${dry_run}" == true ]]; then
  log_warn "Running in dry-run mode. Use --strict to create links/copies."
fi

python3 "${args[@]}"

mkdir -p "${provenance_dir}"
cat > "${trace_file}" <<EOF
timestamp_utc: ${timestamp_utc}
git_commit: ${git_commit}
generated_by: scripts/run/prepare_3dvar_fgat_runtime.sh
inputs:
  manifest: ${manifest}
execution_modes:
  dry_run: ${dry_run}
  copy_mode: ${copy_mode}
  force: ${force}
expected_outputs:
  runtime_tree: build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500
notes:
  - This script prepares the runtime directory from the runtime manifest.
  - This script does not render the PBS job.
  - This script does not submit qsub.
EOF

log_info "Runtime provenance trace written to ${trace_file}"
