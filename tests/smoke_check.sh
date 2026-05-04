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
  docs/first_real_3dvar_fgat_case.md
  configs/sites/jaci/site.env.example
  configs/sites/jaci/README.md
  configs/experiments/3dvar_fgat/experiment.yaml
  configs/experiments/3dvar_fgat/README.md
  configs/experiments/3dvar_fgat/render_context.example.yaml
  configs/experiments/3dvar_fgat/observers.yaml
  configs/experiments/3dvar_fgat/ioda_inventory.example.yaml
  configs/experiments/3dvar_fgat/data_layout.example.yaml
  configs/experiments/3dvar_fgat/staging.example.yaml
  configs/experiments/3dvar_fgat/scientific_input_checklist.yaml
  configs/experiments/3dvar_fgat/runtime_manifest.example.yaml
  configs/experiments/3dvar_fgat/run_command.example.yaml
  configs/experiments/3dvar_fgat/pbs_job.example.yaml
  configs/jedi/applications/3dvar.yaml
  configs/jedi/applications/3dvar_fgat.yaml
  configs/jedi/obs_plugs/variational/aircraft.yaml
  configs/jedi/obs_plugs/variational/sondes.yaml
  configs/jedi/obs_plugs/variational/sfc.yaml
  configs/jedi/obs_plugs/variational/metadata.yaml
  configs/mpas/resources/model.yaml
  configs/templates/resources/forecast.yaml
  configs/templates/resources/variational_minimal.yaml
  configs/templates/import_manifest.yaml
  scripts/env/load_jaci_env.sh
  scripts/setup/check_runtime.sh
  scripts/setup/audit_3dvar_fgat_scientific_inputs.sh
  scripts/setup/bootstrap_3dvar_fgat_data_layout.sh
  scripts/setup/check_external_input_root.sh
  scripts/setup/print_3dvar_fgat_next_steps.sh
  scripts/setup/stage_3dvar_fgat_inputs.sh
  scripts/setup/validate_3dvar_fgat_staged_inputs.sh
  scripts/run/render_3dvar_fgat.sh
  scripts/run/prepare_3dvar_fgat_runtime.sh
  scripts/run/run_3dvar_fgat_variational.sh
  scripts/run/render_3dvar_fgat_pbs.sh
  scripts/run/validate_3dvar_fgat_experiment.sh
  workflow/cylc/global.cylc.jaci.example
  jobs/pbs/smoke_test.pbs
  jobs/pbs/3dvar_fgat.pbs.template
  tools/check_placeholders.py
  tools/check_observer_manifest.py
  tools/check_observer_metadata.py
  tools/check_ioda_inventory.py
  tools/audit_scientific_inputs.py
  tools/bootstrap_data_layout.py
  tools/check_external_input_root.py
  tools/stage_inputs.py
  tools/validate_staged_inputs.py
  tools/render_template.py
  tools/render_observers.py
  tools/prepare_runtime.py
  tools/run_variational.py
  tools/validate_experiment.py
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

echo "[INFO] Checking observer manifest"
python3 tools/check_observer_manifest.py configs/experiments/3dvar_fgat/observers.yaml

echo "[INFO] Checking observer metadata"
python3 tools/check_observer_metadata.py \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml

echo "[INFO] Checking IODA inventory"
python3 tools/check_ioda_inventory.py \
  --inventory configs/experiments/3dvar_fgat/ioda_inventory.example.yaml \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml

echo "[INFO] Checking data layout dry-run"
bash scripts/setup/bootstrap_3dvar_fgat_data_layout.sh --dry-run > /tmp/monan_jedi_data_layout.txt
grep -q "DRY-RUN" /tmp/monan_jedi_data_layout.txt
grep -q "observations/ioda/2024081500" /tmp/monan_jedi_data_layout.txt

echo "[INFO] Checking external input root in permissive mode"
bash scripts/setup/check_external_input_root.sh --allow-missing > /tmp/monan_jedi_external_input_root.txt
grep -q "External input root" /tmp/monan_jedi_external_input_root.txt || grep -q "MONAN_EXTERNAL_DATA_ROOT" /tmp/monan_jedi_external_input_root.txt

echo "[INFO] Auditing scientific input checklist"
bash scripts/setup/audit_3dvar_fgat_scientific_inputs.sh > /tmp/monan_jedi_scientific_inputs.txt
grep -q "Scientific input checklist audit completed" /tmp/monan_jedi_scientific_inputs.txt

echo "[INFO] Checking first-case next steps helper"
bash scripts/setup/print_3dvar_fgat_next_steps.sh > /tmp/monan_jedi_next_steps.txt
grep -q "First real MONAN/JEDI 3DVar-FGAT case" /tmp/monan_jedi_next_steps.txt

echo "[INFO] Checking input staging dry-run"
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run > /tmp/monan_jedi_input_staging.txt
grep -q "Input staging completed" /tmp/monan_jedi_input_staging.txt

echo "[INFO] Checking staged inputs in permissive mode"
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh --allow-missing > /tmp/monan_jedi_staged_inputs.txt
grep -q "Staged input validation passed" /tmp/monan_jedi_staged_inputs.txt

echo "[INFO] Inspecting placeholders"
python3 tools/check_placeholders.py configs/jedi/applications/3dvar.yaml configs/templates/resources/variational_minimal.yaml >/tmp/monan_jedi_placeholders.txt
if [[ ! -s /tmp/monan_jedi_placeholders.txt ]]; then
  echo "[ERROR] Expected placeholders were not reported" >&2
  exit 1
fi

echo "[INFO] Running end-to-end structural experiment validation"
bash scripts/run/validate_3dvar_fgat_experiment.sh > /tmp/monan_jedi_experiment_validation.txt
grep -q "Experiment structural validation passed" /tmp/monan_jedi_experiment_validation.txt

echo "[INFO] Structure smoke check passed"
