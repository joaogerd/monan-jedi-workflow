#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

MANIFEST="${REPO_ROOT}/configs/experiments/3dvar_fgat/obs_conversion.example.yaml"
STRICT=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST="$2"
      shift 2
      ;;
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

cmd=(python3 tools/validate_obs_conversion.py --manifest "${MANIFEST}")

if [[ "${STRICT}" == true ]]; then
  cmd+=(--strict)
fi

"${cmd[@]}"
