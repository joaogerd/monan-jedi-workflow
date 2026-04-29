# Data layout bootstrap

This document describes how to create the directory layout expected by the current
MONAN/JEDI 3DVar-FGAT structural workflow.

The bootstrap command creates directories only. It does not create fake scientific files.

## Files

Layout definition:

```text
configs/experiments/3dvar_fgat/data_layout.example.yaml
```

Tool:

```text
tools/bootstrap_data_layout.py
```

Wrapper:

```text
scripts/setup/bootstrap_3dvar_fgat_data_layout.sh
```

## Dry-run

```bash
bash scripts/setup/bootstrap_3dvar_fgat_data_layout.sh --dry-run
```

This prints the directories that would be created under `${MONAN_DATA_ROOT}`.

## Create directories

After loading the JACI environment:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
bash scripts/setup/bootstrap_3dvar_fgat_data_layout.sh
```

This creates directories such as:

```text
${MONAN_DATA_ROOT}/background/2024081500
${MONAN_DATA_ROOT}/observations/ioda/2024081500
${MONAN_DATA_ROOT}/covariance
${MONAN_DATA_ROOT}/graph
${MONAN_DATA_ROOT}/static
```

## Check expected files

To fail when expected scientific files are missing:

```bash
bash scripts/setup/bootstrap_3dvar_fgat_data_layout.sh --check-files
```

This should be used after background, IODA, covariance, graph and static files have been staged.

## Important caution

The bootstrap step only prepares the filesystem layout. It does not validate:

- MPAS background contents;
- IODA/HDF5 contents;
- covariance compatibility;
- MPAS mesh compatibility;
- graph partition compatibility;
- JEDI YAML scientific correctness.
