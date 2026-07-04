# NMC V1 JACI Smoke

## Validation gates

1. `--dry-run` must produce 18 resolved platform plans and PBS scripts:
   five WPS ungrib stages, five MPAS initialization stages, and eight MPAS forecasts.
2. `--prepare-only` must validate static inputs and materialize links/templates without calling qsub, MPI, WPS, MPAS, or creating `run-state.json`.
3. Before any real PBS submission, inspect the rendered WPS, initialization, and forecast templates.
4. The first real canary is `wps_ungrib_2026062000` followed by `mpas_init_2026062000`.
5. Only after the canary output and CDF5 contract pass should the full five-init/eight-forecast NMC smoke be submitted.

## Forecast template contract

The forecast renderer must replace historical template values with stage values:

- f024 uses `config_run_duration = '1_00:00:00'` or the equivalent stop time;
- f048 uses `config_run_duration = '2_00:00:00'` or the equivalent stop time;
- `config_start_time` uses the stage init time;
- `config_do_restart = false`;
- `config_block_decomp_file_prefix = 'x1.10242.graph.info.part.'`;
- the `input` stream uses `filename_template="init.nc"` and `input_interval="initial_only"`.

## Status

Static JACI preflight passed on commit `d7f2196428857bf3a3bbba97b773806d22c77ec4` in an isolated worktree. Real execution and audit remain pending.
