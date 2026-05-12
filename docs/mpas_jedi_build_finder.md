# MPAS-JEDI build finder on JACI

This document describes the helper used to search for candidate MPAS-JEDI build directories on JACI.

The finder does not modify `configs/sites/jaci/site.env`. It only reports candidates and suggested
values for the user to inspect.

## Files

Finder:

```text
tools/find_mpas_jedi_build.py
```

Wrapper:

```text
scripts/setup/find_mpas_jedi_build.sh
```

## Purpose

The workflow requires a real MPAS-JEDI build before a scientific 3DVar-FGAT run can be submitted.
The important executable for the first variational run is:

```text
mpasjedi_variational.x
```

Other useful executables are:

```text
mpas_atmosphere
mpasjedi_hofx3d.x
```

The finder searches for candidate build directories that contain these executables under `bin/`.

## Basic usage

After loading the JACI environment:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
bash scripts/setup/find_mpas_jedi_build.sh
```

The default search roots are derived from available environment variables such as:

- `MPAS_BUNDLE_BUILD`
- `MONAN_WORK_ROOT`
- `MONAN_WORKFLOW_ROOT`
- `MONAN_JACI_WORKSPACE`

## Search a specific location

```bash
bash scripts/setup/find_mpas_jedi_build.sh ${MONAN_JACI_WORKSPACE}/projects
```

Increase search depth if needed:

```bash
bash scripts/setup/find_mpas_jedi_build.sh --max-depth 7 ${MONAN_JACI_WORKSPACE}/projects
```

## Strict mode

```bash
bash scripts/setup/find_mpas_jedi_build.sh --strict ${MONAN_JACI_WORKSPACE}/projects
```

Strict mode fails if no candidate containing `mpasjedi_variational.x` is found.

## Suggested site.env values

When a 3DVar-capable candidate is found, the finder prints suggested values such as:

```bash
export MPAS_BUNDLE_BUILD="/path/to/build"
export MPASJEDI_VARIATIONAL_EXE="/path/to/build/bin/mpasjedi_variational.x"
export MPAS_ATMOSPHERE_EXE="/path/to/build/bin/mpas_atmosphere"
export MPASJEDI_HOFX_EXE="/path/to/build/bin/mpasjedi_hofx3d.x"
```

These values should be inspected and then copied manually into:

```text
configs/sites/jaci/site.env
```

After editing `site.env`, reload and validate:

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
bash scripts/setup/check_mpas_jedi_build.sh --strict
```

## Current limitations

The finder only checks for executable files under `bin/`. It does not verify:

- that the build was compiled with the correct compiler/MPI stack;
- that it is compatible with the current JEDI YAML;
- that it supports the selected MPAS mesh;
- that SABER/UFO/IODA plugins are scientifically compatible;
- that runtime modules are fully consistent.

Those checks must be addressed during the first real run validation.
