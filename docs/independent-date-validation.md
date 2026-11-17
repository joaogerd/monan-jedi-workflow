# Second independent-date integration test — before scientific validation

The 2025-09-01 00/06Z JACI workflow completed all 24 task validations.
This establishes a working reference *for that period only*. A second,
distinct period is required before we assess scientific diagnostics.

## Scientific independence contract

Every date derives from the requested **first analysis UTC**, including
the previous MPAS Init time (T-6h), initial MPAS FGAT trajectory (T-3h),
first analysis state (T), intermediate cycling trajectory (T+3h) and
second analysis state (T+6h). The first cycle flag in the JEDI application
must also match the chosen first analysis exactly.

Static resources (mesh, invariant, physics tables, covariance B) are shared,
as expected for an unchanged scientific experiment. **No time-dependent**
NetCDF, GRIB, BUFR, IODA, background or analysis may be reused from the
September 2025 case.

## Select a genuinely available second period

On the JACI login node:

```bash
cd /p/projetos/monan_das/joao.gerd/work/first-experiment-20250901-runtime-v2
source ./environment.sh

python -m monan_jedi_workflow.experiment_start "$PWD" --suggest-dates
```

The date discovery requires two consecutive six-hour PREPNR + GPSRO raw files,
and a previous-cycle GFS GRIB. It only reports exact readable file paths
matching the *reference recipe* and does not download, submit or modify data.
If no dates are found, acquire the missing data (or point to an existing,
verified archive) before proceeding. Do not fabricate IODA files or relink
old output to a new date.

For example, **only if the source data exist**, test a leap-day first analysis:

```bash
TEST_DATE=2024-02-29T00:00:00Z
TEST_CASE=/p/projetos/monan_das/$USER/work/first-experiment-independent-20240229
python -m monan_jedi_workflow.experiment_start "$TEST_CASE" --start "$TEST_DATE"
cd "$TEST_CASE"
source ./environment.sh
python -m monan_jedi_workflow.experiment_start "$PWD" --check-inputs
campaign check campaign.yaml
campaign export campaign.yaml --engine simpleworkflow
swf validate workflow.yaml
swf plan workflow.yaml
swf run workflow.yaml --ui plain
```

For dates recommended by `--suggest-dates`, replace both `TEST_DATE` and
the destination directory name accordingly. Choose a **new** directory every
time. The existing successful September case must not be changed.

The dry input check is independent of whether NOAA might offer a download
later: the selected inputs must exist locally before the scientific run.

## Acceptance criteria

1. Source period differs from September 2025, preferably another month/year
   and ideally across a month or year boundary.
2. No hardcoded 2025-09-01 JEDI `first_cycle`, background NetCDF names or
   initialization cycles remain in the created configuration.
3. All 24 generated workflow tasks use the selected period correctly.
4. Input preflight passes using **actual** data for both analyses.
5. WPS/MPAS Init/initial MPAS/Obs2IODA/JEDI/cycling MPAS pass scientific
   *operational validation* for both analysis times.
6. Restart/caching retains already validated previous operations after any
   recoverable failure, without blind scientific job resubmission.

Only after both independent periods complete should the project move to
increment/OmB/OmA, time consistency, background/analysis and other scientific
validation.

Code-level regression tests cover 2024-02-29 (leap date),
2023-01-01 (previous year initialization), and an evening cycle crossing a
day boundary. These tests do not substitute for the JACI execution.
