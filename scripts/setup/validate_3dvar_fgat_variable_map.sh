#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)
cd "${REPO_ROOT}"

source scripts/utils/logging.sh

STRICT=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      STRICT=true
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

PROFILE="${VARIABLE_PROFILE:-tutorial_2024_mpas_8_2_static_b}"
MAP_FILE="${VARIABLE_MAP_FILE:-configs/experiments/3dvar_fgat/variable_map.example.yaml}"

BACKGROUND="${MONAN_SCRATCH}/jaci_3dvar_fgat_tutorial_2018041500/background/mpasout.2018-04-15_00.00.00.nc"
STDDEV="${MONAN_DATA_ROOT}/covariance/mpas.stddev.nc"
NICAS_DIR="${MONAN_DATA_ROOT}/covariance/NICAS"
VBAL_DIR="${MONAN_DATA_ROOT}/covariance/VBAL"

AUXILIARY_FILES=(
  "${MONAN_DATA_ROOT}/static/x1.10242.invariant.nc"
  "${MONAN_DATA_ROOT}/static/x1.static.nc"
  "${MONAN_DATA_ROOT}/static/templateFields.10242.nc"
)

log_info "Validating variable map"
log_info "Variable profile: ${PROFILE}"

cmd=(
python3 tools/validate_variable_map.py
--map "${MAP_FILE}"
--profile "${PROFILE}"
--background "${BACKGROUND}"
--stddev "${STDDEV}"
--nicas-dir "${NICAS_DIR}"
--vbal-dir "${VBAL_DIR}"
)

for aux_file in "${AUXILIARY_FILES[@]}"; do
  cmd+=(--auxiliary "${aux_file}")
done

if [[ "${STRICT}" == true ]]; then
  cmd+=(--strict)
fi

"${cmd[@]}"
