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
  configs/experiments/3dvar_fgat/render_context.example.yaml
  configs/experiments/3dvar_fgat/observers.yaml
  configs/experiments/3dvar_fgat/runtime_manifest.example.yaml
  configs/experiments/3dvar_fgat/run_command.example.yaml
  configs/experiments/3dvar_fgat/pbs_job.example.yaml
  configs/jedi/applications/3dvar.yaml
  configs/jedi/applications/3dvar_fgat.yaml
  configs/jedi/obs_plugs/variational/aircraft.yaml
  configs/jedi/obs_plugs/variational/sondes.yaml
  configs/jedi/obs_plugs/variational/sfc.yaml
  configs/mpas/resources/model.yaml
  configs/templates/resources/forecast.yaml
  configs/templates/resources/variational_minimal.yaml
  configs/templates/import_manifest.yaml
  scripts/env/load_jaci_env.sh
  scripts/setup/check_runtime.sh
  scripts/run/render_3dvar_fgat.sh
  scripts/run/prepare_3dvar_fgat_runtime.sh
  scripts/run/run_3dvar_fgat_variational.sh
  scripts/run/render_3dvar_fgat_pbs.sh
  workflow/cylc/global.cylc.jaci.example
  jobs/pbs/smoke_test.pbs
  jobs/pbs/3dvar_fgat.pbs.template
  tools/check_placeholders.py
  tools/render_template.py
  tools/render_observers.py
  tools/prepare_runtime.py
  tools/run_variational.py
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

echo "[INFO] Rendering 3DVar-FGAT template smoke output"
rm -rf build/rendered
bash scripts/run/render_3dvar_fgat.sh \
  configs/experiments/3dvar_fgat/render_context.example.yaml \
  build/rendered/3dvar_fgat.yaml

grep -q "cost type: 3D-Var" build/rendered/3dvar_fgat.yaml
grep -q "2024-08-15T00:00:00Z" build/rendered/3dvar_fgat.yaml
grep -q "name: aircraft" build/rendered/observers.yaml
grep -q "name: sondes" build/rendered/observers.yaml
grep -q "name: sfc" build/rendered/observers.yaml
grep -q "aircraft_obs_2024081500.h5" build/rendered/3dvar_fgat.yaml
grep -q "sondes_obs_2024081500.h5" build/rendered/3dvar_fgat.yaml
grep -q "sfc_obs_2024081500.h5" build/rendered/3dvar_fgat.yaml

echo "[INFO] Checking runtime preparation dry-run"
bash scripts/run/prepare_3dvar_fgat_runtime.sh > /tmp/monan_jedi_runtime_prep.txt
grep -q "DRY-RUN" /tmp/monan_jedi_runtime_prep.txt
grep -q "background_state" /tmp/monan_jedi_runtime_prep.txt
grep -q "aircraft_ioda" /tmp/monan_jedi_runtime_prep.txt

echo "[INFO] Checking variational command dry-run"
bash scripts/run/run_3dvar_fgat_variational.sh > /tmp/monan_jedi_variational_cmd.txt
grep -q "mpasjedi_variational" /tmp/monan_jedi_variational_cmd.txt
grep -q "Dry-run mode" /tmp/monan_jedi_variational_cmd.txt
grep -q "build/rendered/3dvar_fgat.yaml" build/rendered/mpasjedi_variational.command

echo "[INFO] Rendering PBS job"
bash scripts/run/render_3dvar_fgat_pbs.sh > /tmp/monan_jedi_pbs_render.txt
grep -q "#PBS -N monan_3dvar_fgat" build/rendered/3dvar_fgat.pbs
grep -q "#PBS -l select=1:ncpus=128:mpiprocs=128" build/rendered/3dvar_fgat.pbs
grep -q "run_3dvar_fgat_variational.sh" build/rendered/3dvar_fgat.pbs

echo "[INFO] Structure smoke check passed"
