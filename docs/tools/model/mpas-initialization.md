# MPAS Initialization

## Status

Draft V2 component. YAML-to-stage compilation, explicit runtime staging, local execution, JACI PBS rendering/submission/wait, artifact validation, and NMC campaign planning are implemented and covered by local tests. Real JACI execution and scientific validation remain pending.

## Purpose

`mpas-initialization` creates and validates one initial MPAS state at a specified cycle time. It is the producer of initial conditions for forecast stages used by data-assimilation and NMC B-matrix campaigns.

## Scientific Context

An MPAS forecast must start from a state consistent with the selected mesh, static fields, and cycle time. This component produces that initial state; it does not run the subsequent forecast or assess forecast skill.

## When to Use the Tool

Use this component before any V2 MPAS forecast that depends on an initial state produced by the same workflow. Do not use it to convert observations or run JEDI assimilation.

## Inputs

- a cycle time;
- `model.mpas.initialization_products` with an initial-state path template;
- `model.mpas.initialization` with an explicit command, run directory, optional environment, links, templates, and validation rules.

## Outputs

The stage publishes one initial MPAS state file. Its path is defined by `state_template` and becomes the explicit `{initial_state}` input of forecast staging.

## Artifact Contract

| Artifact | Producer | Consumer | Current validation |
| --- | --- | --- | --- |
| Initial MPAS state | MPAS initialization | MPAS forecast | Exists and is non-empty |
| Initialization log | MPAS initialization | Validation/orchestration | Optional markers |
| PBS script | JACI platform adapter | PBS | Explicit argv/resources |

NetCDF semantic checks for variables, mesh identity, and cycle time remain pending.

## YAML Configuration

A complete component example is at `examples/v2/model/mpas_initialization.yaml.example`; the full workflow example is at `examples/v2/bmatrix/nmc_campaign.yaml.example`.

Supported template tokens are `workspace`, `cycle_time`, `init_time`, `init_yyyymmddhh`, `valid_time`, `valid_yyyymmddhh`, `mpas_valid_file_time`, `lead_hours`, `lead_hours_03d`, `state`, and `run_dir`.

## Parameters

| Parameter | Effect |
| --- | --- |
| `cycle_time` | Initialization time. |
| `state_template` | Expected initial-state path. |
| `run_dir` | Initialization working directory. |
| `argv` | Exact executable arguments. |
| `links` | Inputs staged as idempotent symbolic links. |
| `templates` | Input files rendered from explicit context. |
| `required_log_markers` | Completion markers checked in the selected log. |

## Dependencies

- Python 3.10 or newer;
- MPAS initialization executable and its input data;
- PBS commands when running through the JACI backend.

## CLI Usage

The public workflow command is:

```bash
monan-jedi-workflow-v2 nmc-campaign \
  --config examples/v2/bmatrix/nmc_campaign.yaml.example \
  --workspace /path/to/workspace \
  --dry-run
```

A standalone initialization CLI is not exposed yet; the campaign command invokes the same initialization stage contract.

## simpleWorkflow Usage

The future adapter will call the public V2 workflow CLI with resolved configuration and workspace. It must not embed initialization logic or scheduler commands in workflow YAML.

## ecFlow and Cylc Integration Contract

The orchestration task invokes the same explicit execution request. Queue, module prelude, launcher, and resource settings remain platform configuration.

## Validation

The stage validates link/template sources before execution, then requires the initial-state file and optional log markers after backend completion. Scheduler completion alone is not scientific success.

## Restart and Idempotency Behavior

Matching symbolic links are reused. Regular run-directory targets are not overwritten by staging. The workflow runner revalidates declared outputs before reusing a previous successful state.

## Limitations

- No real JACI initialization evidence yet.
- No NetCDF semantic validation yet.
- No standalone public V2 CLI yet.
- No scientific comparison against an accepted MPAS initialization baseline yet.

## FAQ

### Why is initialization separate from forecast?

The stages publish different scientific products, have different validation contracts, and may have different upstream dependencies. Keeping them separate makes the DAG explicit and allows controlled retries.

### Does a successful initialization guarantee a valid forecast?

No. The forecast stage still validates its own restart/state outputs and has its own runtime contract.

## References

- MPAS-Atmosphere documentation.
- `docs/developers/v2-architecture-and-migration-plan.md`.
