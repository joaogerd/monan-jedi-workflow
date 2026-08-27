# Validated corrected cycling campaign: 2018-04-15 00Z–18Z

## Purpose and status

This document records the first end-to-end **validated corrected cycling
campaign from analysis 00Z through analysis 18Z**. It covers four consecutive
6-hourly analyses spanning the 00/06/12/18 synoptic cycles and the three MPAS
forecast legs that connect them. It is a reproducibility record and evidence
for the workflow's stage contracts; it is not an operational configuration or
a claim that a full 24-hour forecast cycle was completed.

The campaign stops at the validated 18Z analysis. MPAS 18Z→00Z, observations
for the next day, and the next 00Z analysis were not prepared or run.

Recorded workflow revision:

- branch: `agent/cycled-da-simpleworkflow`;
- commit: `d59a151e03290594a31253f0b093c28173b3440c`;
- JACI execution date: 2026-08-27;
- reference metadata: `examples/simpleworkflow/cycled_da/reference-campaign-20180415.yaml`.

## Scope

Analysis cycles:

- `2018-04-15T00:00:00Z`;
- `2018-04-15T06:00:00Z`;
- `2018-04-15T12:00:00Z`;
- `2018-04-15T18:00:00Z`.

External forecast legs:

- 00Z→06Z;
- 06Z→12Z;
- 12Z→18Z.

Obs2IODA conversions were formally validated at 06Z, 12Z, and 18Z. The 00Z
analysis used its already established initial/baseline observation inputs.

## Corrected cycling graph

```text
corrected JEDI00 analysis
  └─ corrected MPAS00→06
       ├─ 03Z: trajectory initial state for JEDI06
       └─ 06Z: analysis base state for JEDI06
            └─ corrected JEDI06 analysis
                 └─ corrected MPAS06→12
                      ├─ 09Z: trajectory initial state for JEDI12
                      └─ 12Z: analysis base state for JEDI12
                           └─ corrected JEDI12 analysis
                                └─ corrected MPAS12→18
                                     ├─ 15Z: trajectory initial state for JEDI18
                                     └─ 18Z: analysis base state for JEDI18
                                          └─ corrected JEDI18 analysis
                                               (campaign terminal analysis)
```

The distinction between the two forecast products matters. For analysis time
`T`, the `T-3h` state initializes the 3D-FGAT background trajectory `xb(t)`;
the `T` state is the complete MPAS state used to initialize the analysis
output. Neither state is a “seed” or “pre-seed”.

## Job ledger

Scheduler state `F` means that PBS retained a finished job; scientific success
comes from exit status, application markers, and the stage validation manifest.

| Stage | Cycle/leg | Job | Exit | Scientific status | Runtime | Main product |
|---|---|---:|---:|---|---|---|
| JEDI | 00Z | `391531.pbs-ha` | 0 | validated | `work/jedi-fgat-corrected/20180415T000000Z` | analysis 00Z |
| MPAS | 00Z→06Z | `394389.pbs-ha` | 0 | validated | `work/mpas-fgat-corrected/20180415T000000Z` | states 03Z/06Z |
| JEDI | 06Z failed attempt | `394656.pbs-ha` | 143 | **operational failure; not a scientific result** | `work/jedi-fgat-corrected/20180415T060000Z` | invalid partial analysis, excluded |
| JEDI | 06Z | `394916.pbs-ha` | 0 | validated | `work/jedi-fgat-corrected/20180415T060000Z` | analysis 06Z |
| MPAS | 06Z→12Z | `395095.pbs-ha` | 0 | validated | `work/mpas-fgat-corrected/20180415T060000Z` | states 09Z/12Z |
| JEDI | 12Z | `397938.pbs-ha` | 0 | validated | `work/jedi-fgat-corrected/20180415T120000Z` | analysis 12Z |
| MPAS | 12Z→18Z | `398188.pbs-ha` | 0 | validated | `work/mpas-fgat-corrected/20180415T120000Z` | states 15Z/18Z |
| JEDI | 18Z | `398258.pbs-ha` | 0 | validated | `work/jedi-fgat-corrected/20180415T180000Z` | analysis 18Z |
| Obs2IODA | 06Z | local converters | 0 | manifest validated | `work/obs2ioda/20180415T060000Z` | sondes/sfc/GNSSRO IODA |
| Obs2IODA | 12Z | local converters | 0 | manifest validated | `work/obs2ioda/20180415T120000Z` | sondes/sfc/GNSSRO IODA |
| Obs2IODA | 18Z | local converters | 0 | manifest validated | `work/obs2ioda/20180415T180000Z` | sondes/sfc/GNSSRO IODA |

Evidence for the failed 06Z attempt is retained under
`.monan-jedi-workflow/failed-attempts/394656.pbs-ha/`. It must not be used as
scientific input.

## Product and SHA-256 ledger

The following hashes were recalculated from the current files during
consolidation. Paths are rooted at `/p/projetos/monan_das/joao.gerd/work/CASE`.

| Role | Product | SHA-256 |
|---|---|---|
| JEDI00 analysis | `work/jedi-fgat-corrected/20180415T000000Z/Data/states/mpas.3dvar.2018-04-15_00.00.00.nc` | `be54bfac20356b524a260593a064d7dd27259982077b2b107d6b35c20f3eb321` |
| JEDI06 trajectory initial state | `work/mpas-fgat-corrected/20180415T000000Z/mpasout.2018-04-15_03.00.00.nc` | `d00b332e76ac83a8fff1d6f49c63f31f79785dc6cb259dd736395fbe9b8756c6` |
| JEDI06 analysis base state | `work/mpas-fgat-corrected/20180415T000000Z/mpasout.2018-04-15_06.00.00.nc` | `d67f6750bc580429a335acf5301d52404d750bcce2e1241d0859d5470208d177` |
| JEDI06 analysis | `work/jedi-fgat-corrected/20180415T060000Z/Data/states/mpas.3dvar.2018-04-15_06.00.00.nc` | `c898fd851bc20794aab660c194fe536abec93d42afd6da4bbe139b253e65201f` |
| JEDI12 trajectory initial state | `work/mpas-fgat-corrected/20180415T060000Z/mpasout.2018-04-15_09.00.00.nc` | `6ac16130d54d418178a3bc84bfe228afb8da921b9c4bbfe47052cc0d6b8e63a0` |
| JEDI12 analysis base state | `work/mpas-fgat-corrected/20180415T060000Z/mpasout.2018-04-15_12.00.00.nc` | `9e3e17068babcae830bbd6f75ab50afb5ad9aa63a0e49f9a66c6b71523b4ea4a` |
| JEDI12 analysis | `work/jedi-fgat-corrected/20180415T120000Z/Data/states/mpas.3dvar.2018-04-15_12.00.00.nc` | `3d6a526782c331175b17401fe233074353c0a360d298c2ed21ea602ec8568400` |
| JEDI18 trajectory initial state | `work/mpas-fgat-corrected/20180415T120000Z/mpasout.2018-04-15_15.00.00.nc` | `cd3d9df4c67aa30d6e348f1a25de5295cb56c2b69714e2d6870ecada821d44d4` |
| JEDI18 analysis base state | `work/mpas-fgat-corrected/20180415T120000Z/mpasout.2018-04-15_18.00.00.nc` | `d64d5fa8cad152832280502da31ebbe59510e4e840f7db3bc98003fb0cf2cfdc` |
| JEDI18 analysis | `work/jedi-fgat-corrected/20180415T180000Z/Data/states/mpas.3dvar.2018-04-15_18.00.00.nc` | `71879efa4069a43da44b6ab7c5ae5e028057572411f84a51307b0700e5fe09f0` |

## Canonical FGAT temporal contract

For an analysis at `T`:

- the observation window is `T-3h` through `T+3h`;
- the external forecast publishes the trajectory initial state at `T-3h`;
- the external forecast publishes the complete analysis base state at `T`;
- OOPS/MPAS-JEDI integrates `xb(t)` internally from `T-3h` to `T+3h`;
- `model.tstep=PT20M` and MPAS `config_dt=1200 s` must describe the same
  physical clock;
- six hours contain 18 `Model::step` transitions and 19 trajectory states;
- `GetValues` uses `nearest`, whose nominal maximum temporal distance on a
  20-minute grid is 600 seconds.

This equality is essential: the OOPS logical clock must advance by exactly the
same elapsed time as the physical MPAS integration.

| Analysis | Window | Physical steps | Logical steps | Physical elapsed | Logical elapsed | GetValues max |
|---|---|---:|---:|---:|---:|---:|
| 00Z | previous day 21Z→03Z | 18 | 18 | 21600 s | 21600 s | 600 s |
| 06Z | 03Z→09Z | 18 | 18 | 21600 s | 21600 s | 600 s |
| 12Z | 09Z→15Z | 18 | 18 | 21600 s | 21600 s | 600 s |
| 18Z | 15Z→21Z | 18 | 18 | 21600 s | 21600 s | 600 s |

Each job produced 2304 `model_propagate` records: 18 steps × 128 MPI ranks.
The step counts, endpoints, and elapsed times were read from the executed logs;
the GetValues bounds were recalculated from the IODA files actually linked to
each runtime.

## Complete-state analysis contract

`analysis_base_state` is the full MPAS background state at analysis time. The
workflow initializes the final analysis file from this state before JEDI
overwrites variables in the analysis stream. The recorded mechanism is:

```text
mpas-workflow-background-copy-overwrite
```

This matters because an analysis-stream-only file is not a complete,
restartable MPAS state. Downstream forecasts must receive the full state, not
only the fields updated by DA.

The 06Z, 12Z, and 18Z states each contain 63 variables: 13 analysis-stream
variables may change and all 50 non-analysis variables were compared and
preserved byte-for-byte. `refl10cm` and `refl10cm_max` were both preserved
exactly. The initial 00Z state is a documented schema variant with 62
variables: 13 analysis variables and 49 exactly preserved non-analysis
variables. It contains `refl10cm_max` but not `refl10cm`; no reflectivity field
was fabricated. Thus every variable present outside the analysis stream was
preserved exactly in every audited cycle.

## Scientific integration contract

The corrected standalone MPAS forecasts and JEDI nonlinear outer models were
audited as scientifically equivalent:

```text
config_dt                       = 1200 s
config_len_disp                 = 240000 m
config_o3climatology            = true
config_physics_suite            = mesoscale_reference
config_horiz_mixing             = 2d_smagorinsky
config_visc4_2dsmag             = 0.05
config_do_DAcycling             = true
config_IAU_option               = off
config_time_integration_order   = 2
config_split_dynamics_transport = true
config_number_of_sub_steps      = 2
config_dynamics_split_steps     = 3
all configured advection orders = 3
config_coef_3rd_order           = 0.25
config_epssm                    = 0.1
config_smdiv                    = 0.1
```

Only natural standalone/JEDI runtime and I/O differences were accepted.
Equivalent spellings such as `1200`/`1200.0` and `true`/`.true.` are not
scientific differences.

## Observation ledger

“Locations in IODA” describes records in the input file. “Processed” is the
number loaded inside the ObsSpace/window. “Final used” counts assimilated
observation values after filters. For Radiosonde, final used is the sum across
air temperature, specific humidity, eastward wind, and northward wind; it is
not a number of physical soundings.

| Cycle | ObsSpace | Locations in IODA | Processed | Final used values |
|---|---|---:|---:|---:|
| 00Z | Radiosonde | 974 | 974 | 1213 |
| 00Z | GnssroRefNCEP | 20 | 20 | 10 |
| 00Z | SfcCorrected | 282 | 252 | 52 |
| 06Z | Radiosonde | 2682 | 2682 | 4532 |
| 06Z | GnssroRefNCEP | 69198 | 68951 | 24099 |
| 06Z | SfcCorrected | 154574 | 138449 | 60594 |
| 12Z | Radiosonde | 69557 | 69557 | 108361 |
| 12Z | GnssroRefNCEP | 76449 | 75956 | 26881 |
| 12Z | SfcCorrected | 159651 | 143061 | 62643 |
| 18Z | Radiosonde | 2431 | 2431 | 3900 |
| 18Z | GnssroRefNCEP | 72986 | 72258 | 23813 |
| 18Z | SfcCorrected | 156421 | 140169 | 61407 |

The large change in the 12Z Radiosonde network is expected for a principal
synoptic cycle. Observation-network changes also explain why cost values must
not be compared as if they were a forecast-skill ranking.

## Cost and convergence diagnostics

| Cycle | Initial nonlinear J | Final nonlinear J | DRPCG iterations | Residual reduction | RMS Δpressure_p | RMS Δtheta | RMS Δu | RMS Δsurface_pressure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 00Z | 918.925 | 601.961 | 10 | 0.0238151 | 23.1409 | 0.502263 | 0.354060 | 35.4208 |
| 06Z | 60771.7 | 40719.0 | 10 | 0.151940 | 39.8924 | 0.684796 | 0.445025 | 68.7457 |
| 12Z | 151741 | 124608 | 10 | 0.334679 | 42.9812 | 0.696073 | 0.581539 | 60.2604 |
| 18Z | 59518.2 | 45593.3 | 10 | 0.184954 | 37.1605 | 0.601820 | 0.438548 | 62.9910 |

**Absolute J values are not directly comparable as forecast or analysis skill
because observation networks and counts differ substantially between cycles.**
The table records convergence behavior and increment scale only; it does not
rank cycles.

## Numerical sanity

All validated corrected analyses had zero audited NaN and Inf values in
`pressure_p`, `rho`, `theta`, `u`, `qv`, `surface_pressure`, `w`, `qc`, `qg`,
`qi`, `qr`, and `qs`. The audited hydrometeors were nonnegative. The 03Z, 06Z,
09Z, 12Z, 15Z, and 18Z forecast states passed the same targeted checks and
showed non-trivial temporal evolution. These statements apply only to the
fields and products that were explicitly audited.

## Failures and lessons learned

### Historical FGAT timestep mismatch

The historical setup combined OOPS `model.tstep=PT45M` with MPAS
`config_dt=1800`, so physical and logical elapsed time diverged. The corrected
contract uses `PT20M == 1200 s`; all four analyses proved 18 physical and 18
logical steps over six hours.

### Inappropriate 480-km tutorial settings

Tutorial values such as `config_len_disp=480000` were not appropriate for the
x1.10242 contract. The corrected campaign consistently used 240000 m and the
same integration physics in JEDI outer trajectories and standalone forecasts.

### Complete analysis output

The analysis file must begin as the full analysis-time MPAS background state.
Copy-then-overwrite preserved all fields outside the analysis stream and made
the analysis suitable for the next forecast leg.

### Missing observation-output parent directory

JEDI06 attempt `394656.pbs-ha` ended with exit 143 because the declared
`Data/os/obsout_*.nc4` parents did not exist. It produced no valid scientific
result. Commit `d59a151e03290594a31253f0b093c28173b3440c` made
`jedi-prepare` create parent directories generically for rendered
`obsdataout.engine.obsfile` destinations. The valid retry was job
`394916.pbs-ha`.

### Obs2IODA RPATH

`obs2ioda_v3` retains an obsolete RPATH into an older `monan-jedi-mpas`
build. Conversions used an explicit loader path after `ldd` showed zero missing
dependencies. This remains an operational debt; no JEDI runtime inherited the
workaround and no rebuild was performed during the campaign.

### Jb diagnostics

Several cycles report nonlinear final `Jb` near `1e-7` while the inner
quadratic `Jb` is finite. The values are retained as a diagnostic question.
This document does not classify the behavior as a bug and the campaign did not
modify OOPS or MPAS-JEDI in response.

## Acceptance checklist

A corrected cycling campaign is accepted when:

1. every scientific job selected as valid exits successfully;
2. every stage validation manifest is valid;
3. JEDI physical and logical trajectory time agree;
4. standalone MPAS and the JEDI nonlinear trajectory share the scientific
   model configuration;
5. observation timestamps satisfy the assimilation window;
6. GetValues timing satisfies the configured interpolation bound;
7. every analysis output is a complete MPAS state;
8. all non-analysis state variables are preserved exactly;
9. analysis variables receive non-trivial increments;
10. audited outputs contain no NaN or Inf values;
11. required forecast states evolve physically;
12. each downstream stage consumes the exact validated upstream product;
13. job and product provenance, including SHA-256, is recorded;
14. repository tests pass and the working tree is clean.

| Criterion | Campaign result |
|---|---|
| Valid scientific PBS jobs exit 0 | PASS; the excluded operational attempt is explicitly identified |
| Validation manifests valid | PASS |
| Physical/logical FGAT clocks agree | PASS in 00Z, 06Z, 12Z, and 18Z |
| MPAS/JEDI scientific settings agree | PASS across all three forecast handoffs |
| Observation windows | PASS |
| Nearest interpolation bound ≤600 s | PASS |
| Complete analysis state | PASS, including documented 00Z schema variant |
| Non-analysis preservation | PASS: 49/49 at 00Z; 50/50 thereafter |
| Non-trivial DA increments | PASS |
| Numerical sanity | PASS for audited fields |
| Forecast evolution | PASS |
| Exact upstream/downstream hashes | PASS |
| Provenance | PASS |
| Tests and clean tree at consolidation | PASS |

The open RPATH and Jb diagnostic questions are non-blocking technical debts;
they do not invalidate the evidence above.

## Reproducibility workflow

Every JACI command starts by entering the controlled environment:

```bash
source /p/projetos/monan_das/joao.gerd/work/CASE/case-enter.sh
```

Use the stage interfaces rather than a single ad hoc campaign script:

```text
obs2ioda-doctor  CASE --cycle TIME
obs2ioda-prepare CASE --cycle TIME
obs2ioda-run      CASE --cycle TIME
obs2ioda-validate CASE --cycle TIME

jedi-prepare  CASE --cycle TIME
jedi-submit   CASE --cycle TIME
jedi-wait     CASE --cycle TIME
jedi-validate CASE --cycle TIME

mpas-prepare  CASE --cycle TIME
mpas-submit   CASE --cycle TIME
mpas-wait     CASE --cycle TIME
mpas-validate CASE --cycle TIME
```

The gate is always `prepare → inspect → submit → wait → validate`. A finished
scheduler job is not promoted until application markers, required outputs,
scientific invariants, and validation manifests pass. Before consuming any
upstream product, resolve its link and recalculate its SHA-256 against the
campaign ledger.

The machine-readable summary is reference metadata only. It does not submit
jobs, replace case configuration, or override runtime manifests.

## Orchestration boundary

`monan-jedi-workflow` owns domain-stage mechanics and contracts: materialized
configuration, input validation, stage execution, manifests, and scientific
validation. An external orchestrator owns dependency order and timing.
simpleWorkflow is the research/reference orchestrator used to demonstrate the
cycle. A future ecFlow integration can consume the same stage-level contracts;
the validated science is not coupled to simpleWorkflow as a mandatory engine.

## Implications for MONAN-JEDI compatibility

Replacing MPAS with MONAN must not silently break the contracts demonstrated
here: state-variable names and semantics, dimensions and staggering, complete
restartable state, `xtime`, model timestep and clock semantics,
`atm_do_timestep`/`Model::step` physical-logical agreement, DA cycling
behavior, diagnostics required by JEDI, and analysis-output restartability.
This campaign is evidence for those compatibility boundaries, not a complete
MONAN-JEDI specification.

