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

## Observation provider configuration — restored GDEX support

The experiment directly invokes `obs convert prepare`, which acquires
only missing inputs for the requested UTC cycle on the JACI login node.

The previous project's proven GDEX downloader (`obs_acquisition.py`) has
been reconnected. It handles direct HTTPS files and **daily GNSS-RO TAR.GZ
archives**, including extracting the exact-cycle BUFR member and writing
`.source.json` provenance.

Default source selection for the first experiment:
- 2025 onward: GDEX d337000 PREPNR hourly URLs
- Before 2025: GDEX d337000 PREP48H hour-specific URLs (distinct conventional
  observation product, explicitly logged and recorded in provenance)
- GNSS-RO: GDEX d735000 daily `gpsro.YYYYMMDD.tar.gz`, with
  `gdas.gpsro.tHHz.YYYYMMDD.bufr` extracted for the selected cycle

**Important:** the 2024 GDEX PREPNR collection is published as a daily
TAR archive, not as the 2025 hourly PREPNR URLs. For the 2024 leap-day
integration test, the downloader therefore selects the available PREP48H
product. It is **not** the same as PREPNR. The original target filename still
follows the reference converter's local input contract; its provenance
records the actual PREP48H source. Do not compare PREPNR versus PREP48H
analyses as scientifically identical without separate assessment.

Users can provide their own `obs2ioda.acquisition.providers` to override
defaults, or `enabled: false` to disable network acquisition.

Historical archive coverage and access remain dependent on GDEX. HTTPS
404 for a date is an actionable missing input; the workflow must not
silently substitute another date. The source provider archive can change.

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
