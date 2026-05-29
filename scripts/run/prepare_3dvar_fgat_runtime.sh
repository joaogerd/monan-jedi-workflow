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
started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
started_epoch=$(date -u +%s)

runtime_tree="${REPO_ROOT}/build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500"
rendered_yaml="${REPO_ROOT}/build/rendered/3dvar_fgat.yaml"

runtime_artifacts=(
  "background/mpasout.2018-04-15_00.00.00.nc"
  "obs/aircraft_obs_2018041500.h5"
  "obs/sondes_obs_2018041500.h5"
  "obs/sfc_obs_2018041500.h5"
  "covariance/mpas.stddev.nc"
  "x1.10242.invariant.nc"
  "x1.10242.graph.info.part.64"
  "templateFields.10242.nc"
  "geovars.yaml"
  "keptvars.yaml"
  "obsop_name_map.yaml"
  "namelist.atmosphere.outer"
  "namelist.atmosphere.inner"
  "streams.atmosphere.outer"
  "streams.atmosphere.inner"
  "stream_list.atmosphere.control"
  "stream_list.atmosphere.background"
  "stream_list.atmosphere.analysis"
  "stream_list.atmosphere.ensemble"
)

git_commit="unknown"
if command -v git >/dev/null 2>&1; then
  git_commit=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || printf 'unknown')
fi

exists_flag() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    printf 'true'
  else
    printf 'false'
  fi
}

file_size_bytes() {
  local path="$1"
  local resolved
  resolved=$(readlink -f "${path}" 2>/dev/null || printf '%s' "${path}")
  if [[ -f "${resolved}" ]]; then
    wc -c < "${resolved}" | tr -d ' '
  else
    printf '0'
  fi
}

sha256_or_missing() {
  local path="$1"
  local resolved
  resolved=$(readlink -f "${path}" 2>/dev/null || printf '%s' "${path}")
  if [[ -f "${resolved}" ]] && command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${resolved}" | awk '{print $1}'
  elif [[ -f "${resolved}" ]]; then
    printf 'sha256sum-not-available'
  else
    printf 'missing'
  fi
}

resolved_path() {
  local path="$1"
  readlink -f "${path}" 2>/dev/null || printf '%s' "${path}"
}

append_artifact_checksum() {
  local label="$1"
  local path="$2"
  cat >> "${trace_file}" <<EOF
  ${label}:
    path: ${path}
    resolved_path: $(resolved_path "${path}")
    exists: $(exists_flag "${path}")
    size_bytes: $(file_size_bytes "${path}")
    sha256: $(sha256_or_missing "${path}")
EOF
}

append_runtime_artifact_checksums() {
  cat >> "${trace_file}" <<EOF
artifact_checksums:
EOF
  append_artifact_checksum "manifest" "${manifest}"
  append_artifact_checksum "rendered_yaml" "${rendered_yaml}"
  for artifact in "${runtime_artifacts[@]}"; do
    local_label=$(printf '%s' "${artifact}" | tr '/.-' '___')
    append_artifact_checksum "${local_label}" "${runtime_tree}/${artifact}"
  done
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
  append_runtime_artifact_checksums
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

log_info "Preparing 3DVar-FGAT runtime"
log_info "Runtime preparation provenance"
log_info "  started UTC   : ${started_at_utc}"
log_info "  git commit    : ${git_commit}"
log_info "  script        : scripts/run/prepare_3dvar_fgat_runtime.sh"
log_info "  manifest      : ${manifest}"
log_info "  runtime tree  : ${runtime_tree}"
log_info "  mode dry-run  : ${dry_run}"
log_info "  mode copy     : ${copy_mode}"
log_info "  mode force    : ${force}"
log_info "  note          : this script prepares runtime files; it does not render PBS"
if [[ "${dry_run}" == true ]]; then
  log_warn "Running in dry-run mode. Use --strict to create links/copies."
fi

mkdir -p "${provenance_dir}"
cat > "${trace_file}" <<EOF
started_at_utc: ${started_at_utc}
git_commit: ${git_commit}
generated_by: scripts/run/prepare_3dvar_fgat_runtime.sh
inputs:
  manifest: ${manifest}
  rendered_yaml: ${rendered_yaml}
execution_modes:
  dry_run: ${dry_run}
  copy_mode: ${copy_mode}
  force: ${force}
command:
  executable: python3
  argv: ${args[*]}
expected_outputs:
  runtime_tree: ${runtime_tree}
  runtime_artifacts:
$(printf '    - %s\n' "${runtime_artifacts[@]}")notes:
  - This script prepares the runtime directory from the runtime manifest.
  - This script does not render the PBS job.
  - This script does not submit qsub.
  - artifact_checksums is written at script exit and resolves symbolic links when possible.
EOF

python3 "${args[@]}"

log_info "Runtime provenance trace written to ${trace_file}"
