# User guide

## Typical 3DVar-FGAT workflow

The current workflow targets the first 3DVar-FGAT case on JACI.

```text
load environment
validate runtime
create data layout
prepare external inputs
stage files
validate scientific inputs
render JEDI YAML
prepare runtime
render PBS job
submit job
```

## Basic command sequence

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
bash scripts/setup/check_runtime.sh configs/sites/jaci/site.env
bash tests/smoke_check.sh
bash scripts/setup/bootstrap_3dvar_fgat_data_layout.sh
bash scripts/setup/create_3dvar_fgat_external_tree.sh
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
bash scripts/setup/stage_3dvar_fgat_inputs.sh
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/run/render_3dvar_fgat.sh
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
bash scripts/run/render_3dvar_fgat_pbs.sh
```

Submit only after all checks pass:

```bash
qsub build/rendered/3dvar_fgat.pbs
```

## Weekly cycling concept

For a one-week experiment with 6-hour cycles, the workflow should eventually expand the period into 28 cycles. Each cycle should run assimilation, then a short MONAN/MPAS forecast to provide the next background.

```text
analysis(cycle N) → short forecast → background(cycle N+1)
```

This cycling layer is planned but not fully implemented yet.
