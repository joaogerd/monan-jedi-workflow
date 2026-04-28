# Variational execution wrapper

This document describes the first safe wrapper for assembling and optionally executing the
`mpasjedi_variational.x` command.

The wrapper is intentionally conservative. By default it only prints the command and writes it to a
file. Real execution requires `--execute`.

## Files

Configuration:

```text
configs/experiments/3dvar_fgat/run_command.example.yaml
```

Tool:

```text
tools/run_variational.py
```

Wrapper:

```text
scripts/run/run_3dvar_fgat_variational.sh
```

## Dry-run

```bash
bash scripts/run/run_3dvar_fgat_variational.sh
```

This writes:

```text
build/rendered/mpasjedi_variational.command
```

and prints the command that would be executed.

## Strict validation

```bash
bash scripts/run/run_3dvar_fgat_variational.sh --strict
```

Strict mode fails if the configured executable or rendered YAML file is missing.

## Real execution

Real execution is disabled by default. To run it:

```bash
bash scripts/run/run_3dvar_fgat_variational.sh --execute
```

Use this only inside a validated runtime directory and usually inside a PBS allocation or job.

## Command configuration

Example:

```yaml
variational_run:
  executable: "${MPASJEDI_VARIATIONAL_EXE}"
  mpi_launcher: "${MPI_LAUNCHER}"
  mpi_tasks: 128
  threads: 1
  work_dir: "build/runtime/jaci_3dvar_fgat_smoke/2024081500"
  yaml: "build/rendered/3dvar_fgat.yaml"
  log_file: "logs/mpasjedi_variational.log"
```

## Current limitations

This wrapper does not yet:

- submit PBS jobs;
- create PBS scripts;
- validate that MPI task count matches graph partition files;
- validate JEDI YAML schema;
- validate MPAS/JEDI executable version;
- parse JEDI logs.

Those are planned as separate layers.
