#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

source "${REPO_ROOT}/scripts/utils/logging.sh"

log_info "Validating MONAN/JEDI 3DVar-FGAT experiment structure"

cd "${REPO_ROOT}"

log_info "Rendering JEDI YAML and observers"
bash scripts/run/render_3dvar_fgat.sh

log_info "Preparing runtime dry-run"
bash scripts/run/prepare_3dvar_fgat_runtime.sh

log_info "Building variational command dry-run"
bash scripts/run/run_3dvar_fgat_variational.sh

log_info "Rendering PBS job"
bash scripts/run/render_3dvar_fgat_pbs.sh

log_info "Running structural validator"
python3 tools/validate_experiment.py \
  --experiment-dir configs/experiments/3dvar_fgat \
  --rendered-dir build/rendered

log_info "3DVar-FGAT experiment validation finished"
