#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

usage() {
  cat <<'EOF'
Usage:
  scripts/run/validate_3dvar_fgat_jedi_observers.sh [--strict]

Optional arguments:
  --jedi-yaml FILE          rendered JEDI YAML
  --observer-manifest FILE  observer manifest YAML
  --ioda-inventory FILE     IODA inventory YAML

Defaults:
  jedi-yaml         = build/rendered/3dvar_fgat.yaml
  observer-manifest = configs/experiments/3dvar_fgat/observers.yaml
  ioda-inventory    = configs/experiments/3dvar_fgat/ioda_inventory.example.yaml
EOF
}

strict=false
jedi_yaml="${REPO_ROOT}/build/rendered/3dvar_fgat.yaml"
observer_manifest="${REPO_ROOT}/configs/experiments/3dvar_fgat/observers.yaml"
ioda_inventory="${REPO_ROOT}/configs/experiments/3dvar_fgat/ioda_inventory.example.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --strict)
      strict=true
      shift
      ;;
    --jedi-yaml)
      jedi_yaml="$2"
      shift 2
      ;;
    --observer-manifest)
      observer_manifest="$2"
      shift 2
      ;;
    --ioda-inventory)
      ioda_inventory="$2"
      shift 2
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

args=(
  "${REPO_ROOT}/tools/validate_jedi_observer_config.py"
  --jedi-yaml "${jedi_yaml}"
  --observer-manifest "${observer_manifest}"
  --ioda-inventory "${ioda_inventory}"
)
if [[ "${strict}" == true ]]; then
  args+=(--strict)
fi

log_info "Validating rendered 3DVar-FGAT JEDI observer configuration"
log_info "JEDI YAML        : ${jedi_yaml}"
log_info "Observer manifest: ${observer_manifest}"
log_info "IODA inventory   : ${ioda_inventory}"
if [[ "${strict}" == true ]]; then
  log_warn "Strict mode enabled. Missing/extra observers will fail."
fi

python3 "${args[@]}"
