# NMC Pairs

## Status

Draft V2 implementation. The stage is locally tested, validates pair geometry, required MPAS products, optional NetCDF artifact contracts, and publishes a stable BFLOW manifest. Real JACI validation and a BFLOW run using the V2 manifest remain pending.

## Purpose

`nmc-pairs` validates already-produced MPAS forecast products and publishes the stable TSV hand-off manifest consumed by BFLOW.

The stage implements the NMC relationship: an older forecast with a longer lead and a newer forecast with a shorter lead must have the same valid time.

## Scientific Context

NMC forecast differences approximate background-error variability from pairs of forecasts valid at the same time. The reliability of later BFLOW processing therefore depends on verified forecast identity, mesh, timing, and NetCDF compatibility.

## When to Use the Tool

Use after MPAS f024/f048 forecasts are available and before BFLOW. It can validate V2-produced products or external pre-existing products when their paths and artifact contracts are explicitly configured.

## Inputs

For every valid time, the stage requires one restart and one MPAS state for f048, plus one restart and one MPAS state for f024.

## Outputs

```text
artifacts/bmatrix/nmc_pairs/
├── bflow-manifest.tsv
└── validation-report.json
```

The manifest has exactly three tab-separated columns:

```text
valid_time    f048    f024
```

## Artifact Contract

| Artifact | Producer | Consumer | Validation |
| --- | --- | --- | --- |
| MPAS restart | MPAS forecast | NMC pairs | Exists/non-empty; optional structure, format, mesh, and time contract |
| MPAS state | MPAS forecast | NMC pairs, BFLOW | Exists/non-empty; optional structure, format, mesh, and time contract |
| BFLOW manifest | NMC pairs | BFLOW | Column order, time ordering, unique times, referenced state files |
| Validation report | NMC pairs | User/orchestrator | Structured JSON report |

The advanced profile can make container format a consumer-facing contract. For example, a BFLOW build that requires CDF5 can reject NetCDF-4 files before any MPI job is submitted.

## YAML Configuration

A standalone example is available at `examples/v2/bmatrix_nmc_pairs/case.yaml.example`.

```yaml
case:
  name: nmc_x1_10242_jun2026

model:
  mpas:
    forecast_products:
      root: /absolute/path/to/mpas/forecasts
      restart_template: "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc"
      state_template: "{init_yyyymmddhh}/f{lead_hours_03d}/mpasout.{mpas_valid_file_time}.nc"

bmatrix:
  nmc_pairs:
    start_valid_time: "2026-06-22T00:00:00Z"
    end_valid_time: "2026-06-25T00:00:00Z"
    interval_hours: 24
    older_lead_hours: 48
    newer_lead_hours: 24
    minimum_pairs: 4
```

Advanced NetCDF checks belong in a science profile, for example `examples/v2/science/mpas_artifact_validation.yaml.example`:

```yaml
model:
  mpas:
    artifact_validation:
      forecast_state:
        consumer: bmatrix.bflow
        accepted_formats: [cdf5]
        required_variables: [xtime]
        required_dimensions:
          nCells: 10242
        required_global_attributes:
          mesh_id: x1.10242
        time_variable: xtime
        require_expected_time: true
```

## Parameters

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `start_valid_time` | ISO-8601 time | required | First inclusive common valid time. |
| `end_valid_time` | ISO-8601 time | required | Last inclusive common valid time. |
| `interval_hours` | integer | `24` | Spacing between common valid times. |
| `older_lead_hours` | integer | `48` | Lead of the earlier forecast. Must exceed `newer_lead_hours`. |
| `newer_lead_hours` | integer | `24` | Lead of the later forecast. |
| `minimum_pairs` | integer | `4` | Required complete pair count; values below four are rejected. |
| `manifest_path` | relative path | `artifacts/bmatrix/nmc_pairs/bflow-manifest.tsv` | Manifest output path in the workflow workspace. |
| `report_path` | relative path | `artifacts/bmatrix/nmc_pairs/validation-report.json` | Report output path in the workflow workspace. |

`artifact_validation.<artifact>` accepts `consumer`, `accepted_formats`, `required_variables`, `required_dimensions`, `required_global_attributes`, `time_variable`, and `require_expected_time`.

## Dependencies

- Python 3.10 or newer;
- PyYAML;
- netCDF4 Python bindings for structural artifact validation;
- already-completed MPAS forecasts.

## CLI Usage

Standalone validation of externally produced products:

```bash
monan-jedi-workflow-v2 nmc-pairs \
  --config examples/v2/bmatrix_nmc_pairs/case.yaml.example \
  --workspace /path/to/nmc-workspace
```

Use `--dry-run` to inspect the plan without checking products or publishing artifacts.

## simpleWorkflow Usage

For a complete V2 campaign, render tasks with `nmc-campaign --render-simpleworkflow`. The generated NMC task calls:

```text
monan-jedi-workflow-v2 stage run --stage nmc_pairs ...
```

It validates all forecast task artifacts before publishing the manifest.

## ecFlow and Cylc Integration Contract

An ecFlow or Cylc NMC task must invoke `stage run --stage nmc_pairs` with the resolved configuration and workspace. Scheduler dependencies establish order; NMC independently validates the products before consuming them.

## Validation and Restart Behavior

The stage validates pair count, ordering, shared valid time, restart/state availability, optional NetCDF format/schema/mesh/time checks, manifest identity, and manifest references.

A successful state is reused only when all planned restart/state products, NetCDF contracts, the manifest contract, manifest state references, and the JSON report still validate.

## Limitations

- Real JACI validation is pending.
- The exact production MPAS variable and mesh contracts must still be confirmed against the selected baseline.
- BFLOW consumption has not yet been executed with a V2-generated manifest.

## FAQ

### Why validate restart files when BFLOW reads MPAS state files?

The restart file is an independent completion product. Requiring it reduces the chance of publishing state from an incomplete or incorrectly staged forecast.

### Why validate CDF5 before BFLOW?

The consumer may be built without NetCDF-4/HDF5 support. A preflight check turns a late parallel I/O failure into an immediate, actionable configuration error.

### Why is the minimum four pairs?

Four complete pairs are the current technical minimum for this workflow. They are not automatically a scientifically sufficient sample for every covariance experiment.

### Can I use leads other than f048 and f024?

Yes, provided the older lead is strictly greater than the newer lead and both forecasts resolve to the same valid time. The manifest labels remain `f048` and `f024` during this transition.

## References

- Parrish, D. F., and Derber, J. C. (1992). The National Meteorological Center's spectral statistical-interpolation analysis system.
- Project V2 architecture and migration plan: `docs/developers/v2-architecture-and-migration-plan.md`.
