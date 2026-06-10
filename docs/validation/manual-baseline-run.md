# Manual baseline validation

This document records manual execution checks for the first validated MONAN-JEDI baseline managed by this repository.

## Validation record

| Field | Value |
| --- | --- |
| Date | 2026-06-10 |
| Reporter | João Gerd Zell de Mattos |
| Repository | `joaogerd/monan-jedi-workflow` |
| Baseline | `3dfgat_mpastatic_x1.10242_2018041500` |
| Method | 3D-FGAT |
| Covariance | MPASstatic |
| Mesh | `x1.10242` |
| Cycle | `2018041500` |
| MPI layout | `np64` |
| Result | Manual JACI execution completed successfully |

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

The rendered PBS script may contain the explicit MPI launch command, but job submission remains a manual user action.

## Post-PR24 JACI execution record

This execution validates the generic PBS renderer merged through PR #24.

```text
job_id: 264572.pbs-ha
login_node: ian05
workdir: /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/rendered
runtime_dir: /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/runtime/3dfgat_mpastatic_x1.10242_2018041500/2018041500
rendered_yaml: /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/rendered/3dfgat_mpastatic_x1.10242_2018041500.yaml
rendered_pbs: /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/rendered/3dfgat_mpastatic_x1.10242_2018041500.pbs
log_file: /p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow_v2/build/runtime/3dfgat_mpastatic_x1.10242_2018041500/2018041500/logs/run_3dfgat_workflow_geometry_background_np64.264572.pbs-ha.log
mpi_ranks: 64
result: success
final_status: Run: Finishing oops::Variational<MPAS, UFO and IODA observations> with status = 0
```

## Generated output files

The successful run generated the following analysis and observation-space output files:

```text
Data/states/mpas.3dfgat.2018-04-15_00.00.00.nc
Data/os/obsout_3dfgat_sondes.nc4
Data/os/obsout_3dfgat_sfc.nc4
Data/os/obsout_3dfgat_gnssroref.nc4
```

Observed file sizes:

```text
Data/states/mpas.3dfgat.2018-04-15_00.00.00.nc: 31M
Data/os/obsout_3dfgat_sondes.nc4: 734K
Data/os/obsout_3dfgat_sfc.nc4: 381K
Data/os/obsout_3dfgat_gnssroref.nc4: 97K
```

## Follow-up recommendation

Future validation records should keep capturing:

```text
commit:
tag:
job_id:
login_node:
runtime_dir:
rendered_yaml:
rendered_pbs:
log_file:
output_files:
result:
```

This will make baseline validation fully auditable and easier to compare when new cycles, observation sets or covariance options are added.
