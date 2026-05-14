# File reference

## Main configuration files

| File | Purpose |
|---|---|
| `configs/sites/jaci/site.env.example` | Example JACI site configuration |
| `configs/sites/jaci/modules.sh` | JACI modules and Anaconda startup |
| `configs/experiments/3dvar_fgat/experiment.yaml` | Base experiment configuration |
| `configs/experiments/3dvar_fgat/input_sources.example.yaml` | Generic real input source registry |
| `configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml` | JACI-specific input source registry |
| `configs/experiments/3dvar_fgat/staging.example.yaml` | Generic staging manifest |
| `configs/experiments/3dvar_fgat/staging.jaci.example.yaml` | JACI-specific staging manifest |
| `configs/experiments/3dvar_fgat/scientific_input_checklist.yaml` | Scientific input checklist |
| `configs/jedi/applications/3dvar_fgat.yaml` | JEDI 3DVar-FGAT template |
| `configs/jedi/obs_plugs/variational/metadata.yaml` | Observer metadata |

## Setup scripts

| Script | Purpose |
|---|---|
| `scripts/setup/check_runtime.sh` | Validate runtime environment |
| `scripts/setup/bootstrap_3dvar_fgat_data_layout.sh` | Create internal data layout |
| `scripts/setup/create_3dvar_fgat_external_tree.sh` | Create external input tree |
| `scripts/setup/stage_3dvar_fgat_inputs.sh` | Link or copy inputs to `MONAN_DATA_ROOT` |
| `scripts/setup/validate_3dvar_fgat_staged_inputs.sh` | Validate staged inputs |
| `scripts/setup/find_mpas_jedi_build.sh` | Search MPAS-JEDI builds |
| `scripts/setup/check_mpas_jedi_build.sh` | Validate configured MPAS-JEDI build |

## Run scripts

| Script | Purpose |
|---|---|
| `scripts/run/render_3dvar_fgat.sh` | Render JEDI YAML |
| `scripts/run/prepare_3dvar_fgat_runtime.sh` | Prepare runtime directory |
| `scripts/run/render_3dvar_fgat_pbs.sh` | Render PBS job |
| `scripts/run/run_3dvar_fgat_variational.sh` | Build or execute the variational command |
