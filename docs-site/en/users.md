# User documentation

## Simple explanation

Users load the environment, provide real scientific input files, run validations and only then submit the PBS job.

The workflow is designed to fail early before expensive HPC jobs are submitted.

## Short command sequence

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
bash tests/smoke_check.sh
bash scripts/setup/create_3dvar_fgat_external_tree.sh
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
bash scripts/setup/stage_3dvar_fgat_inputs.sh
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/run/render_3dvar_fgat.sh
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
bash scripts/run/render_3dvar_fgat_pbs.sh
qsub build/rendered/3dvar_fgat.pbs
```

## Expected inputs

- MPAS background;
- IODA observation files;
- SABER/BUMP covariance;
- graph info;
- static file;
- MPAS-JEDI build.

## Expected outputs

- rendered JEDI YAML;
- rendered observers;
- prepared runtime directory;
- rendered PBS job;
- logs;
- JEDI analysis;
- observation feedback and diagnostics.
