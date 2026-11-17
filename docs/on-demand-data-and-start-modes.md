# Data lifecycle: cold start, warm start, and login-side acquisition

## User contract

The operator selects a UTC cycle and start mode once. The engine creates a
fully dated case, checks required inputs at each dependency boundary, obtains
only missing files from explicitly configured providers, verifies that a
download corresponds to the requested time, and resumes without silently
overwriting scientific output.

The archived reference recipe is not a universal data provider.

## Cold start

For first analysis T, the reference science recipe initializes with GFS at
T-6h:

1. WPS prepare checks the dated GFS GRIB cache. If absent and acquisition is
   configured, it downloads over HTTPS on login to a temporary file; checks
   Content-Length and GRIB signature; then atomically publishes the file.
2. WPS runs link_grib and ungrib in native PBS.
3. MPAS Init prepares first state, then MPAS forecasts T-6h -> T.
4. OBS retrieves raw PREPNR/GNSSRO inputs independently for T and T+6h,
   converts to IODA, and validates. JEDI then assimilates T, MPAS forecasts
   T -> T+6h, and JEDI assimilates T+6h.

No Python interpreter should be required in scientific PBS jobs.

## Warm start (DESIGN / NOT YET IMPLEMENTED)

Two concepts must remain distinct:
- Engine **resume**: reuses prior successful simpleWorkflow tasks and products
  for *the same experiment identity*; already works on JACI.
- Scientific **warm start**: starts a *new experiment* from a supplied compatible
  model restart, or prepared and validated pair of FGAT trajectory (T-3h) and
  analysis-base state (T) with accompanying runtime configuration.

A valid state must be explicitly selected and checked for date/time, mesh,
levels, variable inventory, chemistry/physics compatibility as applicable,
file integrity, and provenance. If using a restart, normal forecast/restart
semantics must be configured; simply bypassing initialization because any
NetCDF file exists is unsafe.

Scientific warm start can bypass GFS/WPS/MPAS Init **only once a verified
initial state exists for T**. It still needs observations for each
assimilation cycle and future boundary-condition inputs required by the
selected forecast configuration.

The current generated `campaign.yaml` always contains cold-start WPS /
MPAS Init / initial MPAS tasks. Do not claim warm start is operational until
its state contract, CLI, checks and scientific validation are implemented.

## Observation provider configuration

The new Obs acquisition hook is called by `obs convert prepare` before
fingerprinting input files. It checks exact cycle-specific paths and can
download missing data via explicitly configured `obs2ioda.acquisition`
providers. Example shape (illustrative, do **not** copy the URL as a real
archive endpoint):

```yaml
obs2ioda:
  acquisition:
    providers:
      - converter: prepbufr-conventional
        url: https://YOUR-VERIFIED-ARCHIVE/{cycle_year}/{cycle_yyyymmddhh}.nr
      - converter: gpsro-gnssro
        url: https://YOUR-VERIFIED-ARCHIVE/{cycle_year}/{cycle_yyyymmddhh}.bufr
```

Archive providers must be genuinely verified and may need authentication,
catalog discovery, renamed products, or access controls. A URL template is
not proof of historical availability. The default catalog intentionally has
no invented observation URL. When no provider exists and a requested raw
file is absent, the stage fails clearly *before submitting conversion jobs*.

Source inputs already present are reused and are never overwritten. New
transfers are staged atomically, checked for Content-Length (and optional
BUFR signature), and protected by file locks. Scientific validation
continues to happen inside Obs2IODA.

For arbitrary dates, guarantee *correct temporal resolution and clear
failures*, not universal data availability. The historical GFS endpoint is
separate from the archived PREPNR/GNSSRO providers and is expected to have
its own coverage/access rules.

## Remaining acceptance tests

- Unit/fixture tests for GFS and OBS acquisition and failure conditions.
- Real JACI run for a different date with verified raw observation providers.
- Real cold-start confirmation that no manually seeded GFS/BUFR is needed
  for an archive date that supports downloads.
- Verified scientific warm-start implementation and reproducibility.
- Only then move to scientific assessment of increments, departures and
  analysis quality.

Current work adds automatic GFS acquisition and provider-configured OBS
acquisition. **It does not claim warm-start support nor a universal
historical observation archive connector.**
