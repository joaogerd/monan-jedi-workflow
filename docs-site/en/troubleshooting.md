# FAQ and troubleshooting

## `SyntaxError: future feature annotations is not defined`

Likely cause: the system Python is too old.

Solution:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
```

This loads Anaconda and activates the expected Python runtime.

## `MONAN_EXTERNAL_DATA_ROOT is not set`

Likely cause: an old local `site.env` file.

Solution:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
echo $MONAN_EXTERNAL_DATA_ROOT
```

The environment loader should provide a default value when possible.

## Missing IODA files

Check the external input root and staging plan:

```bash
bash scripts/setup/check_external_input_root.sh --allow-missing
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
```

## Missing MPAS-JEDI build

Search for candidates:

```bash
bash scripts/setup/find_mpas_jedi_build.sh --max-depth 7 ${MONAN_JACI_WORKSPACE}/projects
```

Then update `MPAS_BUNDLE_BUILD` in `configs/sites/jaci/site.env`.

## PBS job is rendered but should not be submitted yet

Before submitting, run strict validation commands:

```bash
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/setup/check_mpas_jedi_build.sh --strict
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
```

## Real data should not be committed

NetCDF, HDF5, graph info and model outputs should remain in data areas, not in the Git repository.
