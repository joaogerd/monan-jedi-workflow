# MPAS Forecast

## Status

Draft V2 component. Product-location, staging, output validation, and JACI PBS rendering are implemented and locally tested. A full JACI submission backend, YAML compiler, real MPAS execution, and scientific validation remain pending.

## Purpose

The MPAS forecast component defines one forecast as an explicit contract:

- initialization time and lead time;
- expected restart and MPAS state artifacts;
- deterministic run directory;
- staged links and rendered templates;
- explicit program argument vector;
- declared output and log markers.

The component never infers paths from the current directory and does not contain PBS queue logic.

## Inputs

- an initialization time;
- a positive lead time;
- MPAS restart/state path templates;
- declared link and template inputs;
- an explicit executable argument vector.

## Outputs

A successful forecast must publish at least:

```text
restart.<valid-time>.nc
mpasout.<valid-time>.nc
```

The exact paths are defined by `model.mpas.forecast_products` and become inputs to downstream JEDI or NMC-pair stages.

## Artifact Contract

| Artifact | Producer | Consumer | Current validation |
| --- | --- | --- | --- |
| Restart | MPAS forecast | NMC pairs | Exists and is non-empty |
| MPAS state | MPAS forecast | NMC pairs, JEDI | Exists and is non-empty |
| Model log | MPAS forecast | validation/orchestration | Optional declared markers |
| PBS script | JACI platform adapter | PBS | Explicit argv and resources |

NetCDF variables, dimensions, mesh identity, time coordinate, and container-format checks are not implemented yet.

## Configuration

The current V2 public contract accepts documented path-template tokens:

```text
init_time
init_yyyymmddhh
valid_time
valid_yyyymmddhh
mpas_valid_file_time
lead_hours
lead_hours_03d
```

Unknown tokens fail at configuration construction.

## Parameters

| Parameter | Type | Effect |
| --- | --- | --- |
| `init_time` | UTC time | Forecast initialization. |
| `lead_hours` | positive integer | Forecast lead and valid time. |
| `restart_template` | path template | Expected restart location. |
| `state_template` | path template | Expected MPAS state location. |
| `argv` | list of strings | Exact executable arguments. |
| `required_log_markers` | list of strings | Completion markers checked in a declared log. |

## Dependencies

- Python 3.10 or newer;
- MPAS executable and runtime inputs supplied by the site;
- JACI PBS only when using the JACI adapter.

## CLI Usage

There is no public MPAS V2 CLI yet. The component is intentionally available through the stage and platform contracts while the YAML compiler and workflow builder are completed.

## simpleWorkflow Usage

The future simpleWorkflow task must invoke the public MPAS V2 CLI with an explicit configuration and workspace. It must not embed MPAS run logic in the workflow YAML.

## ecFlow and Cylc Integration Contract

ecFlow and Cylc tasks will render or invoke the same explicit request. Queue resources, module prelude, and launcher remain platform configuration; artifact contracts remain component configuration.

## Validation

The current component validates staged source existence, restart/state file presence, file size, and optional log markers. A scheduler completion state alone is never scientific success.

## Restart and Idempotency Behavior

Matching symbolic links are reused. A regular target is never silently overwritten. Templates are rendered deterministically from an explicit context. Output validation must pass before a workflow runner can reuse a prior successful state.

## Limitations

- No V2 JACI submission/wait backend yet.
- No V2 MPAS initialization stage yet.
- No public YAML compiler or CLI for the forecast stage.
- No JACI or scientific baseline validation yet.

## FAQ

### Why is PBS not inside the MPAS component?

MPAS is scientific capability; PBS is a JACI deployment detail. Keeping them separate allows a local runner, simpleWorkflow, ecFlow, Cylc, or another scheduler to use the same forecast contract.

### Why require both restart and state products?

The state is the downstream analysis or BFLOW input. The restart is an independent completion artifact that helps detect partial or incorrectly staged forecasts.

## References

- MPAS-Atmosphere documentation.
- Project V2 architecture and migration plan: `docs/developers/v2-architecture-and-migration-plan.md`.
