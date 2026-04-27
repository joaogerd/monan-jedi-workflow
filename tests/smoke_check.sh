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
  docs/upstream_audit.md
  docs/upstream_configuration_map.md
  configs/sites/jaci/site.env.example
  configs/sites/jaci/README.md
  configs/experiments/3dvar_fgat/experiment.yaml
  configs/experiments/3dvar_fgat/README.md
  configs/jedi/applications/3dvar.yaml
  configs/mpas/resources/model.yaml
  configs/templates/resources/forecast.yaml
  configs/templates/resources/variational_minimal.yaml
  configs/templates/import_manifest.yaml
  scripts/env/load_jaci_env.sh
  scripts/setup/check_runtime.sh
  workflow/cylc/global.cylc.jaci.example
  jobs/pbs/smoke_test.pbs
  tools/check_placeholders.py
)

for path in "${required_paths[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "[ERROR] Missing required path: $path" >&2
    exit 1
  fi
done

echo "[INFO] Checking imported template provenance"

grep -q "Source: NCAR/MPAS-Workflow" configs/jedi/applications/3dvar.yaml
grep -q "Source: NCAR/MPAS-Workflow" configs/mpas/resources/model.yaml
grep -q "Source: NCAR/MPAS-Workflow" configs/templates/resources/forecast.yaml

echo "[INFO] Inspecting placeholders"
python3 tools/check_placeholders.py configs/jedi/applications/3dvar.yaml configs/templates/resources/variational_minimal.yaml >/tmp/monan_jedi_placeholders.txt
if [[ ! -s /tmp/monan_jedi_placeholders.txt ]]; then
  echo "[ERROR] Expected placeholders were not reported" >&2
  exit 1
fi

echo "[INFO] Structure smoke check passed"
