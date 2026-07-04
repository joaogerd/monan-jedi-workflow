# MPAS Forecast

## Status

Draft V2 component. Product paths, staging, output validation, local execution, JACI PBS rendering/submission/wait, YAML-to-stage compilation, upstream initialization wiring, and optional structural NetCDF contracts are implemented and covered by local tests. Real JACI validation and scientific baseline comparison remain pending.

## Purpose

Defines one MPAS forecast through explicit time, artifact, runtime, and validation contracts.

## Scientific Context

Forecast states provide backgrounds for JEDI and f024/f048 samples for NMC B-matrix production. Scheduler completion is not scientific success.

## When to Use the Tool

Use for a reproducible MPAS forecast after an upstream initialization stage has produced initial conditions.

## Inputs

Initialization time, positive lead, restart/state templates, staged inputs, an explicit executable argument vector, and optionally an explicitly supplied upstream `initial_state` artifact.

## Outputs

A successful forecast publishes restart and MPAS state products.

## Artifact Contract

| Artifact | Consumer | Current validation |
| --- | --- | --- |
| Initial MPAS state | MPAS forecast | Declared link source exists; optional NetCDF contract |
| Restart | NMC pairs | Exists/non-empty; optional NetCDF contract |
| MPAS state | JEDI, NMC pairs, BFLOW | Exists/non-empty; optional NetCDF contract |
| Model log | Validation/orchestration | Optional markers |
| PBS script | PBS | Explicit argv/resources |

A structural contract can require accepted container formats, variables, dimensions, global mesh metadata, and the expected valid time before a downstream stage consumes the artifact.

## YAML Configuration

The compiler reads `model.mpas.forecast_products` and `model.mpas.forecast`. Product roots must be absolute paths; `run_dir` may be relative to the explicit workflow workspace. A component example is available at `examples/v2/model/mpas_forecast.yaml.example`; a full campaign example is available at `examples/v2/bmatrix/nmc_campaign.yaml.example`.

Supported path tokens are `workspace`, `run_dir`, `init_time`, `init_yyyymmddhh`, `valid_time`, `valid_yyyymmddhh`, `mpas_valid_file_time`, `lead_hours`, `lead_hours_03d`, `restart`, `state`, and `initial_state` when supplied by a workflow planner.

Optional advanced checks live under `model.mpas.artifact_validation.forecast_restart` and `model.mpas.artifact_validation.forecast_state`. See `examples/v2/science/mpas_artifact_validation.yaml.example`.

## Parameters

| Parameter | Effect |
| --- | --- |
| `init_time` | Forecast initialization. |
| `lead_hours` | Forecast lead and valid time. |
| `restart_template` | Expected restart path. |
| `state_template` | Expected state path. |
| `argv` | Exact executable arguments. |
| `links` | Idempotent staged inputs, including optional initial state. |
| `artifact_validation` | Optional NetCDF format, schema, metadata, and time checks. |

## Dependencies

Python 3.10+, netCDF4 Python bindings, MPAS runtime inputs, and PBS commands on JACI.

## CLI Usage

The public workflow command is:

```bash
monan-jedi-workflow-v2 nmc-campaign \
  --config examples/v2/bmatrix/nmc_campaign.yaml.example \
  --workspace /path/to/workspace \
  --dry-run
```

A standalone `mpas-forecast` V2 CLI is not exposed yet; the workflow command compiles and invokes the same stage contract.

## simpleWorkflow Usage

Render the campaign with `nmc-campaign --render-simpleworkflow`; each generated forecast task calls `stage run` with the resolved configuration and workspace.

## ecFlow and Cylc Integration Contract

Tasks use the same explicit request and `stage run` contract; platform resources remain outside the component.

## Validation

Checks staged sources, restart/state existence and size, optional log markers, and configured NetCDF format/schema/metadata/time requirements. Backend completion alone is never scientific success.

## Restart and Idempotency Behavior

Matching links are reused; regular targets are never overwritten; successful state reuse requires output validation.

## Limitations

The exact production variable, dimension, mesh-attribute, and time contracts must be confirmed against the selected MPAS baseline. Real JACI execution evidence and scientific baseline comparison are still pending.

## FAQ

### Why is PBS outside the component?

PBS is a site deployment detail, while MPAS is a scientific capability.

### Why require restart and state?

State is consumed downstream; restart independently confirms forecast completion.

### Why validate the format before BFLOW?

A consumer can reject an otherwise valid NetCDF file when its build lacks support for a container format such as NetCDF-4/HDF5. Declaring CDF5 early prevents a late MPI I/O failure.

## References

- MPAS-Atmosphere documentation.
- `docs/developers/v2-architecture-and-migration-plan.md`.
