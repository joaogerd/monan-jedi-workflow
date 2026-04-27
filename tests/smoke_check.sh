#!/usr/bin/env bash
set -euo pipefail

echo "[INFO] Checking repository structure"

required_paths=(
  README.md
  docs/architecture.md
  docs/configuration.md
  docs/mpas_configuration.md
  docs/jedi_configuration.md
  docs/jaci_setup.md
  configs/sites/jaci/site.env.example
  configs/experiments/3dvar_fgat/experiment.yaml
  scripts/env/load_jaci_env.sh
  scripts/setup/check_runtime.sh
  workflow/cylc/global.cylc.jaci.example
  jobs/pbs/smoke_test.pbs
)

for path in "${required_paths[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "[ERROR] Missing required path: $path" >&2
    exit 1
  fi
done

echo "[INFO] Structure smoke check passed"
