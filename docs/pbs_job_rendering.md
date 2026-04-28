# PBS job rendering

This document describes the first PBS job rendering layer for MONAN-JEDI-WORKFLOW.

The goal is to generate an inspectable PBS job script for the JACI 3DVar-FGAT workflow without
submitting it automatically.

## Files

Render context:

```text
configs/experiments/3dvar_fgat/pbs_job.example.yaml
```

PBS template:

```text
jobs/pbs/3dvar_fgat.pbs.template
```

Wrapper:

```text
scripts/run/render_3dvar_fgat_pbs.sh
```

Rendered output:

```text
build/rendered/3dvar_fgat.pbs
```

## Render

```bash
bash scripts/run/render_3dvar_fgat_pbs.sh
```

This command only renders the PBS script. It does not call `qsub`.

## Submit manually after inspection

After reviewing the generated file on JACI:

```bash
qsub build/rendered/3dvar_fgat.pbs
```

## Current PBS workflow inside the job

The rendered PBS job performs the following steps:

1. enters the repository root;
2. loads the JACI site environment if `configs/sites/jaci/site.env` exists;
3. renders the 3DVar-FGAT JEDI YAML;
4. prepares the runtime directory in strict mode;
5. calls the variational wrapper in execution mode.

## Important caution

The generated PBS job is not yet a production job. It still depends on:

- validated JACI module configuration;
- real `MONAN_DATA_ROOT` and `MONAN_SCRATCH` paths;
- a compiled MPAS-JEDI bundle;
- valid IODA observation files;
- valid background states;
- valid SABER/BUMP covariance files;
- graph/static files compatible with the chosen mesh and MPI task count.

## Next development steps

1. Add `qsub` wrapper with default dry-run behavior.
2. Add PBS job validation without submitting.
3. Add JACI-specific queue/account presets.
4. Add checks for `qsub`, `qstat` and PBS environment variables.
5. Later integrate this with Cylc instead of manual PBS submission.
