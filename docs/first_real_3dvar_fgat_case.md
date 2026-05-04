# First real 3DVar-FGAT case on JACI

This document describes the operational preparation sequence for the first real MONAN/JEDI
3DVar-FGAT case on JACI.

The current workflow is structurally ready, but scientific execution still depends on real input
files and a validated MPAS-JEDI installation.

## 1. Load the JACI environment

```bash
cd /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

Expected checks:

```bash
bash scripts/setup/check_runtime.sh configs/sites/jaci/site.env
bash tests/smoke_check.sh
```

Warnings about missing MPAS-JEDI executables, Cylc or scientific input files are expected until
those components are installed and staged.

## 2. Confirm the external input root

```bash
echo ${MONAN_EXTERNAL_DATA_ROOT}
bash scripts/setup/check_external_input_root.sh --allow-missing
```

Create the source directory tree for the first cycle:

```bash
mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/background/2024081500
mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/observations/ioda/2024081500
mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/covariance
mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/graph
mkdir -p ${MONAN_EXTERNAL_DATA_ROOT}/static
```

## 3. Place the real scientific files

The first case currently expects these files under `${MONAN_EXTERNAL_DATA_ROOT}`:

```text
background/2024081500/mpasout.2024-08-15_00.00.00.nc
observations/ioda/2024081500/aircraft_obs_2024081500.h5
observations/ioda/2024081500/sondes_obs_2024081500.h5
observations/ioda/2024081500/sfc_obs_2024081500.h5
covariance/mpas.stddev.nc
graph/graph.info.part.0128
static/x1.static.nc
```

The required files for the current skeleton are:

```text
background_state
aircraft_ioda
sondes_ioda
sfc_ioda
covariance_stddev
```

The graph and static files are currently contextual/optional in the checklist, but they may become
required depending on the final MPAS-JEDI geometry and runtime configuration.

## 4. Dry-run staging

Before creating links or copies:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
```

This command should show planned links from `${MONAN_EXTERNAL_DATA_ROOT}` into `${MONAN_DATA_ROOT}`.

## 5. Stage inputs

Default action is symbolic link:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh
```

To copy instead of linking:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --copy
```

To replace existing targets:

```bash
bash scripts/setup/stage_3dvar_fgat_inputs.sh --force
```

Use `--force` carefully.

## 6. Validate staged inputs

Permissive check:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh --allow-missing
```

Strict check:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
```

Strict mode should pass only after required files have been staged.

## 7. Validate IODA inventory

```bash
python3 tools/check_ioda_inventory.py \
  --inventory configs/experiments/3dvar_fgat/ioda_inventory.example.yaml \
  --manifest configs/experiments/3dvar_fgat/observers.yaml \
  --metadata configs/jedi/obs_plugs/variational/metadata.yaml \
  --strict-files
```

This confirms that required IODA files exist for enabled observers.

## 8. Audit scientific readiness

```bash
bash scripts/setup/audit_3dvar_fgat_scientific_inputs.sh
```

The checklist status fields must be updated as files move from pending to validated states.

Use strict audit only after updating the checklist:

```bash
bash scripts/setup/audit_3dvar_fgat_scientific_inputs.sh --strict
```

## 9. Render workflow products

```bash
bash scripts/run/render_3dvar_fgat.sh
bash scripts/run/prepare_3dvar_fgat_runtime.sh
bash scripts/run/render_3dvar_fgat_pbs.sh
```

At this stage, `prepare_3dvar_fgat_runtime.sh` may still be run without `--strict` for inspection.
Use strict mode only when all required files are present:

```bash
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
```

## 10. Final pre-PBS checks

Before the first real `qsub`, confirm:

```bash
bash scripts/setup/check_runtime.sh configs/sites/jaci/site.env
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/run/validate_3dvar_fgat_experiment.sh
cat build/rendered/3dvar_fgat.pbs
cat build/rendered/3dvar_fgat.yaml
```

Do not submit until:

- `MPAS_BUNDLE_BUILD` points to a real MPAS-JEDI build;
- `MPASJEDI_VARIATIONAL_EXE` exists and is executable;
- required input files are present;
- observer plugs are replaced or validated against real UFO/IODA contents;
- covariance resources match the geometry;
- PBS queue/account values are correct;
- the rendered JEDI YAML has been inspected.

## Current boundary

This guide prepares the system for a real case. It does not guarantee scientific correctness. The
next development stage should add NetCDF/HDF5-aware validation and replace the current structural
observer skeletons with validated UFO/JEDI observer configurations.
