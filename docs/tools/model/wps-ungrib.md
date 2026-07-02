# WPS Ungrib

## Purpose

Converts declared GRIB inputs into the WPS `FILE:YYYY-MM-DD_HH` intermediate consumed by the MPAS global initialization path.

## Scientific Context

This workflow uses the WPS intermediate directly through `config_met_prefix = 'FILE'`. It does not run `metgrid` for this MPAS initialization path.

## Inputs

- Explicit GRIB files staged as `GRIBFILE.*`.
- A compatible Vtable.
- A rendered `namelist.wps` when required by the selected WPS executable.

## Outputs

One declared `FILE:` intermediate artifact per initialization time.

## Artifact Contract

The output is written directly to `model.wps.ungrib_products.root` using `intermediate_template`. MPAS initialization receives that exact artifact through `model.mpas.initialization.wps_input.target`.

## YAML Configuration

See `examples/v2/bmatrix/nmc_campaign.yaml.example`.

## Parameters

`intermediate_template` supports `init_time`, `init_yyyymmddhh`, and `wps_time`. `wps_time` renders `YYYY-MM-DD_HH`.

## Dependencies

WPS `ungrib.exe`, valid GRIB input, Vtable, and the selected execution platform.

## CLI Usage

Use the public NMC campaign CLI; it plans or runs one WPS stage per initialization time.

## simpleWorkflow Usage

The generated WPS task precedes its matching MPAS initialization task.

## ecFlow and Cylc Integration Contract

Use the same `wps_ungrib(cycle) -> mpas_init(cycle)` dependency.

## Validation

Checks staged input files, the required `FILE:` product, and optional log markers.

## Restart and Idempotency Behavior

Links are idempotent. A valid published `FILE:` artifact can be reused; missing output invalidates reuse.

## Limitations

Static geography is an external MPAS initialization input in V1. The real-case Vtable and baseline forcing coverage still require JACI validation.

## FAQ

### Why does this not run metgrid?

The target MPAS initialization consumes the WPS intermediate directly; creating a metgrid product would not satisfy the real consumer contract.

## References

- WPS User's Guide.
- MPAS-Atmosphere initialization configuration.
