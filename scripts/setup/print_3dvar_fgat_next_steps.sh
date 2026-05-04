#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
# First real MONAN/JEDI 3DVar-FGAT case: next steps

1. Load JACI environment

   source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env

2. Create external input directories

   mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/background/2024081500
   mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/observations/ioda/2024081500
   mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/covariance
   mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/graph
   mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/static

3. Place real files under ${MONAN_EXTERNAL_DATA_ROOT}

   background/2024081500/mpasout.2024-08-15_00.00.00.nc
   observations/ioda/2024081500/aircraft_obs_2024081500.h5
   observations/ioda/2024081500/sondes_obs_2024081500.h5
   observations/ioda/2024081500/sfc_obs_2024081500.h5
   covariance/mpas.stddev.nc
   graph/graph.info.part.0128
   static/x1.static.nc

4. Dry-run staging

   bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run

5. Stage files

   bash scripts/setup/stage_3dvar_fgat_inputs.sh

6. Validate staged inputs

   bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh

7. Validate IODA inventory

   python3 tools/check_ioda_inventory.py \
     --inventory configs/experiments/3dvar_fgat/ioda_inventory.example.yaml \
     --manifest configs/experiments/3dvar_fgat/observers.yaml \
     --metadata configs/jedi/obs_plugs/variational/metadata.yaml \
     --strict-files

8. Render and inspect

   bash scripts/run/render_3dvar_fgat.sh
   bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
   bash scripts/run/render_3dvar_fgat_pbs.sh
   cat build/rendered/3dvar_fgat.yaml
   cat build/rendered/3dvar_fgat.pbs

Do not submit PBS jobs until MPAS-JEDI executables, inputs, covariance and observers are validated.
EOF
