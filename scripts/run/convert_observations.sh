#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

cd "${REPO_ROOT}"

source scripts/utils/logging.sh

MANIFEST="${REPO_ROOT}/configs/experiments/3dvar_fgat/obs_conversion.example.yaml"
TRACE="${REPO_ROOT}/build/rendered/provenance/obs_conversion.trace"
EXECUTE=false
STRICT=false
ONLY_ARGS=()

usage() {
  cat <<EOF
Usage:
  scripts/run/convert_observations.sh [options]

Options:
  --manifest FILE   Observation conversion manifest
  --trace FILE      Provenance trace output
  --execute         Run conversion commands. Default only plans commands.
  --strict          Fail on missing raw observation files or outputs.
  --only NAME       Convert/check only one observation entry. May be repeated.
  -h, --help        Show this help.

Defaults:
  manifest = configs/experiments/3dvar_fgat/obs_conversion.example.yaml
  trace    = build/rendered/provenance/obs_conversion.trace
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST="$2"
      shift 2
      ;;
    --trace)
      TRACE="$2"
      shift 2
      ;;
    --execute)
      EXECUTE=true
      shift
      ;;
    --strict)
      STRICT=true
      shift
      ;;
    --only)
      ONLY_ARGS+=(--only "$2")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$(dirname "${TRACE}")"

log_info "Preparing observation conversion stage"
log_info "Manifest: ${MANIFEST}"
log_info "Trace: ${TRACE}"
log_info "Execute: ${EXECUTE}"
log_info "Strict: ${STRICT}"

cmd=(
  python3 tools/run_obs_conversion.py
  --manifest "${MANIFEST}"
  --trace "${TRACE}"
)

if [[ "${EXECUTE}" == true ]]; then
  cmd+=(--execute)
fi

if [[ "${STRICT}" == true ]]; then
  cmd+=(--strict)
fi

if [[ ${#ONLY_ARGS[@]} -gt 0 ]]; then
  cmd+=("${ONLY_ARGS[@]}")
fi

"${cmd[@]}"
