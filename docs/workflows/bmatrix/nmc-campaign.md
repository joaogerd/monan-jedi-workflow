# NMC Campaign Workflow

## Status

Draft V2 workflow. The planner, local execution path, JACI PBS backend, artifact wiring, and dry-run CLI are implemented. A real JACI campaign, NetCDF semantic checks, and a BFLOW run using the V2 manifest remain pending.

## Purpose

The NMC campaign workflow composes MPAS initialization, f024/f048 forecasts, and NMC manifest publication for static B-matrix preparation.

## Scientific Context

For each common valid time, the workflow creates an older forecast with a longer lead and a newer forecast with a shorter lead. Their shared valid-time state products are then published to BFLOW through a validated manifest.

## When to Use the Workflow

Use this workflow to prepare validated NMC pairs before BFLOW. Do not use it for an operational JEDI analysis cycle or direct observation conversion.

## Graph

```text
mpas_init(init_time)
    ↓
mpas_forecast(init_time, lead_hours)
    ↓
nmc_pairs
    ↓
bflow-manifest.tsv
```

For the four-pair f048/f024 example, the planner creates five initialization stages, eight forecast stages, and one NMC hand-off stage.

## Inputs

- `model.mpas.initialization_products` and `model.mpas.initialization`;
- `model.mpas.forecast_products` and `model.mpas.forecast`;
- `bmatrix.nmc_pairs` time window and lead-time relationship.

## Outputs

```text
initial MPAS states
forecast restart files
forecast MPAS state files
artifacts/bmatrix/nmc_pairs/bflow-manifest.tsv
artifacts/bmatrix/nmc_pairs/validation-report.json
```

## Artifact Contract

The planner supplies the initialization product to each forecast using `{initial_state}`. The DAG also records the initialization stage as a dependency of that forecast, so path wiring and scheduler dependency agree.

## YAML Configuration

Use `examples/v2/bmatrix/nmc_campaign.yaml.example` as the complete starting point.

## Parameters

The workflow combines the parameters documented in:

- `docs/tools/model/mpas-initialization.md`;
- `docs/tools/model/mpas-forecast.md`;
- `docs/tools/bmatrix/nmc-pairs.md`.

## Dependencies

- Python 3.10 or newer;
- MPAS initialization and forecast executables;
- site runtime inputs and static files;
- JACI PBS commands for JACI execution.

## CLI Usage

```bash
monan-jedi-workflow-v2 nmc-campaign \
  --config examples/v2/bmatrix/nmc_campaign.yaml.example \
  --workspace /path/to/nmc-campaign \
  --dry-run
```

Remove `--dry-run` only after adapting paths, executable commands, and validation markers to the selected site.

## simpleWorkflow Usage

The adapter must render one task for every V2 stage in the neutral DAG. The task commands must invoke the public V2 CLI/stage contract rather than duplicate MPAS commands inside simpleWorkflow YAML.

## ecFlow and Cylc Integration Contract

The same graph can be rendered as ecFlow triggers or Cylc dependencies. Each forecast task depends on its matching initialization task; the NMC task depends on all forecast tasks.

## Validation

The workflow validates stage products, not only scheduler status. NMC publication requires all expected restart and state files before it writes the BFLOW manifest.

## Restart and Idempotency Behavior

The local runner revalidates prior successful outputs before skipping a stage. Missing initialization, forecast, or manifest products invalidate reuse.

## Limitations

- No real JACI execution evidence yet.
- No MPAS NetCDF semantic/mesh/time validation yet.
- No V2 BFLOW consumption test yet.
- The public campaign CLI currently uses the local backend; JACI backend selection through case configuration is pending.

## FAQ

### Why does the workflow create five initializations for four valid times?

The f048/f024 windows overlap but require initialization times from two days before the first valid time through one day before the last valid time. Those unique initialization times are shared by forecasts when applicable.

### Can a forecast use an initial state outside this workflow?

Yes, but then it should be modeled as an external artifact with an explicit validation contract. The current NMC campaign planner intentionally requires in-workflow initialization coverage.

## References

- Parrish, D. F., and Derber, J. C. (1992). The National Meteorological Center's spectral statistical-interpolation analysis system.
- `docs/developers/v2-architecture-and-migration-plan.md`.
