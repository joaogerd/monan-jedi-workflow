# Regression audit: native scientific PBS environment after app separation

## Observed failure

Reference first-experiment 2025-08-31 18Z, MPAS Init:

- Native PBS job: `826106.pbs-ha`
- PBS: `job_state = F`, `Exit_status = 127`
- CPU consumption: 0, wall time approximately 1 second
- Every one of 128 ranks reported:
  `./mpas_init_atmosphere: error while loading shared libraries: libfabric.so.1`
- `MONAN_LIBFABRIC_ROOT=/opt/cray/libfabric/1.22.0/lib64` was valid on login.
- Generated PBS contained direct `mpiexec` but did not source the scientific
  stack/setup or explicitly establish `LD_LIBRARY_PATH`.

The executable did not begin; missing NetCDF and success marker were
consequences, not independent scientific failures.

## Code comparison

The `main` branch already provides:

- `monan_jedi_workflow/site.py:render_site_environment_block()`: applies
  JACI's site setup, `module purge`, `STACK_SITE_SETUP`,
  `STACK_MODULE_ROOT`, `STACK_ENV_MODULE` and module loading, then
  configures paths for the installed MONAN-JEDI binaries and libraries.
- `monan_jedi_workflow/site.py:runtime_contract_context()`: validates
  installed ecosystem runtime manifest v2, avoiding hardcoded stack choices.
- `monan_jedi_workflow/render.py:render_pbs()`: supports a
  `pbs.bootstrap` block that runs before launching the scientific command.

The branch introduced `catalog/reference-20250901` and Python domain
apps, including the MPAS Init stage. Its example YAML declared
`pbs.launcher`, `pbs.command`, and a few environmental variables but
**no complete stack/bootstrap sequence**. The new `_render_pbs()`
preserved only those declarations and invoked MPI directly.

A second portability regression was a **hardcoded Cray PALS 1.6 launcher**
(`/opt/cray/pals/1.6/bin/mpiexec`) in four new science recipes instead of
letting the loaded site profile choose `mpiexec`. The fixed recipe now uses
the generic launcher and relies on the configured site modules.

The primary regression is thus **a missing connection between the
native stage PBS generation and the existing site bootstrap contract**.
The failure is not evidence that the September GFS, MPAS grid, B matrix
or JEDI observations are invalid.

The packaged September 2025 reference case exists in the branch but
not in `main`; scientific equivalence with earlier successfully executed
cases must be established separately, based on archived actual run inputs,
not inferred from code alone.

## Correction

- `scientific_environment.py` reuses `site.py` to render a
  site-selected native shell environment *on login*, no Python in compute.
- `mpas_stage.py` and `jedi_stage.py` insert the shared site bootstrap
  **before** the native launcher. `init_stage.py` uses the MPAS renderer.
- `native_pbs.py` uses the same bootstrap for WPS and Obs2IODA.
- Native MPI recipes use the site-provided `mpiexec` instead of an
  embedded PALS version. Users may override the launcher per site.
- The installed example now creates one `science/site.yaml` per experiment
  and references it in every native stage via `pbs.site_config`.
- The reference site profile explicitly sets `validate_python: false` to
  avoid Python on the compute nodes.
- `pbs_runtime_library_lines()` retains the optional declared
  `MONAN_LIBFABRIC_ROOT` check for actionable errors, but this alone
  does **not** substitute for full module/stack initialization.

This is a configuration-driven runtime bootstrap, not a fixed
`/opt/cray` path or experiment-specific patch.

## Validation and limitations

Unit tests verify every stage references the same site profile and
that MPAS and JEDI insert module loading before the MPI launcher.
The JACI execution itself remains unverified until the user pulls the
branch and executes the tests on login.

The existing case contains an invalid operation and a completed failed
PBS job; it must not be automatically resubmitted or silently rewritten.
Use a new reference case destination for controlled validation and
keep the older logs/manifest for provenance.

If `MONAN_JEDI_INSTALL_ROOT/share/monan-jedi/install-manifest.json`
does not exist, site profile rendering will fail **before PBS submission**
with a description of the missing runtime contract. That needs an
explicit supported installation/profile correction; do not silently
choose a different stack.
