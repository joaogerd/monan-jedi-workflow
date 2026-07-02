# NMC Campaign Workflow

## Status

Draft V2 workflow. The campaign now includes an explicit WPS `ungrib` producer when `model.wps` is declared, in addition to MPAS initialization, forecasts, NMC publication, JACI dry-run evidence, and persisted campaign audit. A real JACI campaign and BFLOW compatibility probe remain pending.

## Purpose

The NMC campaign prepares f024/f048 forecast pairs for static B-matrix production. For the MPAS global initialization configuration used here, WPS `ungrib` creates the `FILE:YYYY-MM-DD_HH` intermediate product consumed directly by `init_atmosphere`.

## Scientific Context

The forcing path is:

```text
explicit GFS or reanalysis GRIB
  → WPS ungrib
  → FILE:YYYY-MM-DD_HH
  → MPAS init_atmosphere
  → f024/f048 MPAS forecasts
  → NMC pairs
  → bflow-manifest.tsv
```

`metgrid` is intentionally not included in this V1 path because the accepted MPAS initialization configuration uses `config_met_prefix = 'FILE'` and consumes the WPS intermediate directly. `geogrid` is not re-run per cycle; static geography remains an explicit external MPAS initialization input.

## When to Use the Workflow

Use this workflow to produce validated NMC pairs before BFLOW. Do not use it for an operational JEDI analysis cycle or direct observation conversion.

## Graph

For the four-pair f048/f024 example with WPS enabled, the workflow has five `wps_ungrib` stages, five initialization stages, eight forecasts, and one NMC hand-off stage: 19 stages in total.

## Inputs

- `model.wps.ungrib_products` and `model.wps.ungrib`;
- explicit GRIB input files and a Vtable;
- `model.mpas.initialization_products` and `model.mpas.initialization`;
- `model.mpas.forecast_products` and `model.mpas.forecast`;
- `bmatrix.nmc_pairs` time window and lead-time relationship;
- JACI site policy when using `--backend jaci-pbs`.

## Outputs

```text
WPS FILE:YYYY-MM-DD_HH intermediate products
initial MPAS states
forecast restart files
forecast MPAS state files
artifacts/bmatrix/nmc_pairs/bflow-manifest.tsv
artifacts/bmatrix/nmc_pairs/validation-report.json
.monan-jedi-workflow/validation/nmc-campaign.json
```

## Artifact Contract

`model.wps.ungrib.grib_inputs` declares every GRIB input and its conventional `GRIBFILE.*` staging target. `ungrib` must publish its `FILE:` product directly in the declared product directory. The NMC planner adds one explicit link from that product to the matching initialization run directory using `model.mpas.initialization.wps_input.target`, which must begin with `FILE:`.

The WPS-to-init dependency is part of the scheduler-neutral DAG; an init cannot consume a `FILE:` artifact without its matching WPS producer having validated it.

## YAML Configuration

Use `examples/v2/bmatrix/nmc_campaign.yaml.example`. The key relationship is:

```yaml
model:
  wps:
    ungrib_products:
      root: /absolute/path/to/wps-products
      intermediate_template: "{init_yyyymmddhh}/FILE:{wps_time}"
    ungrib:
      run_dir: "/absolute/path/to/wps-products/{init_yyyymmddhh}"
      grib_inputs:
        - source: "/absolute/path/to/gfs/{init_yyyymmddhh}/gfs.pgrb2.0p25.f000"
          target: GRIBFILE.AAA

  mpas:
    initialization:
      wps_input:
        target: "FILE:{wps_time}"
```

Scientific YAML declares stage resources only. Queue routing, MPI launcher syntax, environment modules, and filesystem policy remain in the JACI profile.

## Parameters

- `intermediate_template` supports `init_time`, `init_yyyymmddhh`, and `wps_time`.
- `wps_time` renders `YYYY-MM-DD_HH`.
- `grib_inputs` must use explicit `GRIBFILE.*` targets.
- `wps_input.target` must render to a file name starting with `FILE:`.

## Dependencies

- Python 3.10 or newer;
- WPS `ungrib.exe` and an appropriate Vtable;
- explicit GFS or reanalysis files;
- MPAS initialization and forecast executables;
- netCDF4 Python bindings for MPAS artifact validation;
- JACI PBS commands for JACI execution.

## CLI Usage

JACI dry-run:

```bash
monan-jedi-workflow-v2 nmc-campaign \
  --config examples/v2/bmatrix/nmc_campaign.yaml.example \
  --config examples/v2/platforms/jaci.yaml.example \
  --workspace /path/to/nmc-campaign \
  --backend jaci-pbs \
  --dry-run
```

The dry-run writes plan JSON and PBS evidence for all WPS, initialization, and forecast stages. It does not submit jobs.

After completion, audit existing artifacts:

```bash
python -m monan_jedi_workflow.cli_validate_nmc \
  --config /path/to/case.yaml \
  --config /path/to/jaci.yaml \
  --config /path/to/science.yaml \
  --workspace /path/to/nmc-campaign \
  --backend jaci-pbs
```

The audit returns `0` only when every WPS, MPAS, and NMC output contract validates.

## simpleWorkflow Usage

The renderer emits one `stage run` task per declared WPS, initialization, forecast, and NMC stage. The WPS task is a direct dependency of its matching initialization task.

## ecFlow and Cylc Integration Contract

ecFlow and Cylc must retain the same edge: `wps_ungrib(cycle) → mpas_init(cycle)`. They must not emulate the dependency through an undocumented shared path.

## Validation and Restart Behavior

WPS validates the published `FILE:` product and optional log markers. MPAS initialization validates its state and optional NetCDF contract. The local runner revalidates outputs before reuse and reruns downstream stages after an upstream artifact is regenerated.

## Limitations

- Real JACI evidence is pending.
- Static geography still needs an explicit real-case contract in the smoke configuration.
- The exact baseline NetCDF contract for NMC/BFLOW remains to be confirmed against accepted production files.
- BFLOW has not yet consumed a V2-generated manifest.

## FAQ

### Why is metgrid absent?

The MPAS global initialization configuration in this workflow consumes the WPS `FILE:` intermediate directly. Adding metgrid would create an unused product and obscure the real contract.

### Is geogrid a per-cycle task?

No. For this V1 workflow, static geography is an external MPAS initialization input. It must be declared and validated, but is not regenerated with every NMC cycle.

### Why require GRIBFILE targets?

They make the WPS staging contract explicit and prevent `link_grib.csh` or shell-generated links from becoming hidden workflow dependencies.

## References

- WPS documentation.
- MPAS-Atmosphere initialization documentation.
- `docs/developers/v2-architecture-and-migration-plan.md`.
