# First-use JACI onboarding and persistent site profile

**New users must not need a prior experiment or pre-existing site.yaml.**

The initial `experiment create` now tries to bootstrap the workspace profile
automatically from the installed MONAN-JEDI ecosystem contract v2, the one
available spack-stack installation, and real scientific data paths. It saves
`/p/projetos/<group>/<user>/site.yaml` once, and uses it to generate both
the case's scientific `science/site.yaml` and its `environment.sh`.

## Start in a clean JACI login terminal

```bash
conda activate monan-jedi
experiment create /p/projetos/monan_das/$USER/work/test-new-date \
  --start 2026-01-30T00:00:00Z --mode cold
cd /p/projetos/monan_das/$USER/work/test-new-date
source ./environment.sh
experiment check campaign.yaml
```

If the workspace contains **exactly one** valid spack-stack and the installed
MONAN-JEDI prefix, its runtime manifest, and all input roots exist, no
additional steps are necessary.

If multiple stacks exist, `experiment create` lists candidates, refuses to
select silently, and creates **no experiment directory**. Select the installed
runtime once, using actual paths reported by the tool:

```bash
cd /p/projetos/monan_das/$USER
experiment site init --stack /p/.../work/SELECTED-STACK/spack-stack
experiment create /p/projetos/monan_das/$USER/work/test-new-date \
  --start 2026-01-30T00:00:00Z
```

If the MONAN-JEDI install is not at the documented default, add
`--install /path/to/installed/monan-jedi` to `experiment site init`.
No paths are fabricated, and the command refuses to overwrite an existing
profile. If scientific input directories are absent, the error identifies
each missing root rather than silently creating fake directories.

For a non-standard JACI layout, a verified, existing site profile may be
passed via `experiment create ... --site /absolute/site.yaml`.

The v2 producer manifest is authoritative for the JACI setup script,
module tree and module identity. `science/site.yaml` describes the
runtime selected for PBS jobs. `environment.sh` exports the same paths
in a fresh login shell. It does not attempt to execute scientific modules
inside a Conda controller.

Successful experiments from 2024, 2025 and 2026 are not modified or
rewritten by this onboarding flow.

Regression tests:

```bash
python -m pytest tests/test_site_profile_persistence.py \
  tests/test_unified_cli.py tests/test_experiment_start.py \
  tests/test_scientific_environment.py -q
```
