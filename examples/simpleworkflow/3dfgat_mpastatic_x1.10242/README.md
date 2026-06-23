# simpleWorkflow example: 3D-FGAT MPASstatic x1.10242

This example wraps the validated `3dfgat_mpastatic_x1.10242_2018041500`
MONAN-JEDI baseline with `simpleWorkflow` artifact tracking and provenance.

It intentionally keeps JACI/PBS details inside an explicit shell wrapper. The
`simpleWorkflow` engine remains responsible only for dependency ordering,
artifact validation, task signatures, reuse decisions and immutable attempt
records.

## Execution model

The first four tasks are safe preparation tasks:

1. `validate_config`
2. `prepare_runtime`
3. `render_yaml`
4. `render_pbs`

The `run_3dvar_fgat` task must be executed from inside an already allocated PBS
job on JACI. This avoids treating `qsub` submission as a successful model run.
The wrapper exit code is therefore the real `mpirun/mpasjedi_variational.x` exit
code.

## Local preparation

From the root of `monan-jedi-workflow`:

```bash
simpleworkflow plan examples/simpleworkflow/3dfgat_mpastatic_x1.10242/workflow.yaml \
  --workdir build/simpleworkflow-state/3dfgat_mpastatic_x1.10242

simpleworkflow run examples/simpleworkflow/3dfgat_mpastatic_x1.10242/workflow.yaml \
  --workdir build/simpleworkflow-state/3dfgat_mpastatic_x1.10242 \
  --dry-run
```

## JACI execution

Inside an allocated PBS job, run:

```bash
simpleworkflow run examples/simpleworkflow/3dfgat_mpastatic_x1.10242/workflow.yaml \
  --workdir build/simpleworkflow-state/3dfgat_mpastatic_x1.10242
```

The workflow writes its own immutable attempt records under the selected
`--workdir`, while the MPAS-JEDI log is declared as a required output under
`build/simpleworkflow/3dfgat_mpastatic_x1.10242_2018041500/logs/`.

## Important assumptions

- The rendered MPAS-JEDI YAML and PBS are still produced by `monan-jedi-workflow`.
- This example does not introduce a PBS backend for `simpleWorkflow`.
- The wrapper expects `mpirun` and the JACI environment to be available from the
  surrounding PBS allocation or site setup.
- The executable path in `workflow.yaml` follows the documented JACI convention
  and may need to be edited for another user or installation.
