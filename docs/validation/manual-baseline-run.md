# Manual baseline validation

This document records manual execution checks for the first validated MONAN-JEDI baseline managed by this repository.

## Validation record

| Field | Value |
| --- | --- |
| Date | 2026-06-09 |
| Reporter | João Gerd Zell de Mattos |
| Repository | `joaogerd/monan-jedi-workflow` |
| Baseline | `3dfgat_mpastatic_x1.10242_2018041500` |
| Method | 3D-FGAT |
| Covariance | MPASstatic |
| Mesh | `x1.10242` |
| Cycle | `2018041500` |
| MPI layout | `np64` |
| Result | Manual test completed successfully |

## Scope validated

The successful manual test confirms that the baseline workflow can move beyond static validation and rendering and execute correctly in the intended operational environment.

The validation covers the baseline configuration currently represented by:

```text
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/
```

The baseline uses the compact fragment selectors for variables and observations, which are resolved by the workflow before validation and rendering.

## Expected safe pre-run checks

Before a real execution, the following safe checks should pass:

```bash
make install
make test
make validate
make render-yaml
make render-pbs
```

These commands install the package, run tests, validate the baseline configuration and render the MPAS-JEDI YAML/PBS files. They do not submit jobs or execute MPAS-JEDI.

## Real execution policy

Real MPAS-JEDI execution must remain manual and explicit.

The workflow repository must not automatically call:

```text
qsub
mpiexec
mpirun
mpasjedi_variational.x
```

## Details not yet recorded

The manual test was reported as successful, but the following execution details were not recorded in this first validation note:

- JACI login node used;
- PBS job ID;
- exact branch or commit checked out locally;
- path of the rendered YAML used in the execution;
- path of the rendered PBS script used in the execution;
- runtime directory path;
- final log excerpt;
- list of generated output files.

Future validation records should include these fields when available.

## Follow-up recommendation

For the next real run, capture a short execution record containing:

```text
commit:
job_id:
runtime_dir:
rendered_yaml:
rendered_pbs:
log_file:
result:
```

This will make the baseline validation fully auditable and easier to compare when new cycles, observation sets or covariance options are added.
