# NMC Pairs

## Status

Draft V2 implementation. The stage is locally tested but is **not complete**: it has not yet been validated on JACI, does not run MPAS forecasts, and does not inspect the semantic NetCDF content of the MPAS state files.

## Purpose

`nmc-pairs` validates already-produced MPAS forecast products and publishes the stable TSV hand-off manifest consumed by the future BFLOW stage.

The stage implements the traditional NMC relationship: an older forecast with a longer lead and a newer forecast with a shorter lead must have the same valid time.

## Scope

This tool:

- resolves f048 and f024 product paths from a documented MPAS layout;
- requires a non-empty restart and MPAS state file for every forecast member;
- requires at least four complete pairs for B-matrix calibration;
- writes a `bflow-manifest.tsv` file and JSON validation report;
- records persistent stage state through the V2 local runner.

This tool does not initialize or execute MPAS. Those responsibilities belong to upstream MPAS stages.

## Inputs

For every valid time, the tool requires:

- one f048 restart file;
- one f048 MPAS state file;
- one f024 restart file;
- one f024 MPAS state file.

The state files are published in the manifest because BFLOW consumes them. Restart files are retained as an independent completion check.

## Outputs

By default, outputs are written below the explicit workflow workspace:

```text
artifacts/bmatrix/nmc_pairs/
├── bflow-manifest.tsv
└── validation-report.json
```

The manifest has exactly three tab-separated columns:

```text
valid_time    f048    f024
```

`f048` is the earlier forecast state and `f024` is the later forecast state.

## Artifact Contract

| Artifact | Producer | Consumer | Format | Required validation |
| --- | --- | --- | --- | --- |
| MPAS restart | MPAS forecast | NMC pairs | NetCDF | Exists and is non-empty |
| MPAS state | MPAS forecast | NMC pairs, BFLOW | NetCDF | Exists and is non-empty |
| BFLOW manifest | NMC pairs | BFLOW | TSV | Columns, ordering, unique valid times, referenced files |
| Validation report | NMC pairs | User or orchestration layer | JSON | Written after successful pair validation |

NetCDF structure and format compatibility checks will be added before the stage is marked complete.

## YAML Configuration

A standalone example is available at `examples/v2/bmatrix_nmc_pairs/case.yaml.example`.

```yaml
case:
  name: nmc_x1_10242_jun2026

model:
  mpas:
    forecast_products:
      root: /path/to/mpas/forecasts
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

## Parameters

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `start_valid_time` | ISO-8601 time | required | First inclusive common valid time. |
| `end_valid_time` | ISO-8601 time | required | Last inclusive common valid time. Must align with `interval_hours`. |
| `interval_hours` | integer | `24` | Spacing between common valid times. |
| `older_lead_hours` | integer | `48` | Lead of the earlier forecast. Must exceed `newer_lead_hours`. |
| `newer_lead_hours` | integer | `24` | Lead of the later forecast. |
| `minimum_pairs` | integer | `4` | Required complete pair count; values below four are rejected. |
| `manifest_path` | relative path | `artifacts/bmatrix/nmc_pairs/bflow-manifest.tsv` | Manifest output path in the workflow workspace. |
| `report_path` | relative path | `artifacts/bmatrix/nmc_pairs/validation-report.json` | Report output path in the workflow workspace. |

The MPAS path templates accept only `init_time`, `init_yyyymmddhh`, `valid_time`, `valid_yyyymmddhh`, `mpas_valid_file_time`, `lead_hours`, and `lead_hours_03d`.

## Dependencies

- Python 3.10 or newer;
- PyYAML;
- already-completed MPAS forecasts;
- no external scheduler is required for local validation.

## CLI Usage

```bash
monan-jedi-workflow-v2 nmc-pairs \
  --config examples/v2/bmatrix_nmc_pairs/case.yaml.example \
  --workspace /path/to/nmc-workspace
```

Use `--dry-run` to inspect the planned stage without checking products or writing outputs. Use `--force` to rerun after a successful state record.

## simpleWorkflow Usage

A simpleWorkflow task calls the same public CLI command with explicit arguments:

```yaml
- name: nmc_pairs
  argv:
    - monan-jedi-workflow-v2
    - nmc-pairs
    - --config
    - "{case_config}"
    - --workspace
    - "{workflow_workspace}"
```

The task must depend on the upstream MPAS forecast tasks that produce all requested f024 and f048 files.

## ecFlow and Cylc Integration Contract

An ecFlow or Cylc task must invoke the same CLI command and declare the MPAS state products as inputs and `bflow-manifest.tsv` as its output. Scheduler-specific retry policy must not bypass the stage output validation.

## Validation and Restart Behavior

The stage validates every pair before publication. A successful state is reused only when the manifest and all referenced state files still validate. Removing or truncating an input state file therefore invalidates reuse and causes a new validation attempt.

## Limitations

- MPAS initialization and forecast execution are not yet part of this stage.
- JACI validation is pending.
- MPAS NetCDF variables, dimensions, time coordinates, mesh identity, and format policy are not yet validated.
- BFLOW consumption has not yet been executed with a V2-generated manifest.

## FAQ

### Why validate restart files when BFLOW reads MPAS state files?

The restart file is an independent completion product. Requiring it reduces the chance of publishing a state file from an incomplete or incorrectly staged forecast.

### Why is the minimum four pairs?

The project currently treats four complete pairs as the minimum technical threshold for B-matrix calibration. It is a software guard, not a claim that four samples are scientifically sufficient for every experiment.

### Can I use leads other than f048 and f024?

Yes, provided the older lead is strictly greater than the newer lead and both forecasts resolve to the same valid time. The manifest labels remain `f048` and `f024` for compatibility during this transition; general lead labels will be addressed before BFLOW V1 is declared complete.

## References

- Parrish, D. F., and Derber, J. C. (1992). The National Meteorological Center's spectral statistical-interpolation analysis system.
- Project V2 architecture and migration plan: `docs/developers/v2-architecture-and-migration-plan.md`.
