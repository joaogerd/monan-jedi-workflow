# MPAS Forecast

## Status

Draft V2 component. Product paths, staging, output validation, local execution, JACI PBS rendering, submission, scheduler wait, YAML-to-stage compilation, and upstream initialization wiring are implemented and covered by local tests. Real JACI validation and scientific validation remain pending.

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
| Initial MPAS state | MPAS forecast | Declared link source exists |
| Restart | NMC pairs | Exists and is non-empty |
| MPAS state | JEDI, NMC pairs | Exists and is non-empty |
| Model log | Validation/orchestration | Optional markers |
| PBS script | PBS | Explicit argv/resources |

NetCDF semantic and format validation is pending.

## YAML Configuration

The compiler reads `model.mpas.forecast_products` and `model.mpas.forecast`. A complete component example is available at `examples/v2/model/mpas_forecast.yaml.example`; a full initialization-to-NMC example is available at `examples/v2/bmatrix/nmc_campaign.yaml.example`.

Supported path tokens are `workspace`, `run_dir`, `init_time`, `init_yyyymmddhh`, `valid_time`, `valid_yyyymmddhh`, `mpas_valid_file_time`, `lead_hours`, `lead_hours_03d`, `restart`, `state`, and `initial_state` when supplied by a workflow planner.

## Parameters

| Parameter | Effect |
| --- | --- |
| `init_time` | Forecast initialization. |
| `lead_hours` | Forecast lead and valid time. |
| `restart_template` | Expected restart path. |
| `state_template` | Expected state path. |
| `argv` | Exact executable arguments. |
| `links` | Idempotent staged inputs, including optional initial state. |

## Dependencies

Python 3.10+, MPAS runtime inputs, and PBS commands on JACI.

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

The future adapter will invoke the public workflow CLI with explicit configuration and workspace. It must not reimplement model staging in workflow YAML.

## ecFlow and Cylc Integration Contract

Tasks use the same explicit request; platform resources remain outside the component.

## Validation

Checks staged sources, restart/state existence and size, and optional log markers. Backend completion alone is never scientific success.

## Restart and Idempotency Behavior

Matching links are reused; regular targets are never overwritten; successful state reuse requires output validation.

## Limitations

No real JACI execution evidence, NetCDF semantic validation, or scientific baseline comparison yet.

## FAQ

### Why is PBS outside the component?

PBS is a site deployment detail, while MPAS is a scientific capability.

### Why require restart and state?

State is consumed downstream; restart independently confirms forecast completion.

## References

- MPAS-Atmosphere documentation.
- `docs/developers/v2-architecture-and-migration-plan.md`.
