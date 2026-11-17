# Persistent JACI site profile (one-time configuration)

This workflow previously required every new terminal to inherit `STACK_ROOT`
from a successfully run case because `experiment create` generated an
environment by attempting a heuristic search among possibly multiple
`spack-stack*/spack-stack` directories.

The original runtime design (commits 6513f553 and 1c547885, Sept 2026)
is maintained: **one `site.yaml` describes the machine**, while
`MONAN-JEDI/share/monan-jedi/install-manifest.json` (ecosystem contract v2)
defines the site setup script, module environment/name and module root.

## Save the profile only once on the login node

In a terminal where a validated case has been sourced and all scientific
roots are available:

```bash
cd /p/projetos/monan_das/$USER/work/independent-date-20260129
source ./environment.sh
experiment site save
```

The command validates the input roots and the installed runtime contract v2,
then creates the workspace-wide file **exclusively** at:

```text
/p/projetos/monan_das/<group>/<user>/site.yaml
```

It refuses to overwrite an existing file. This is a site-wide user profile
on JACI, not an experiment case and not a source-code repository file.

The resulting YAML resembles:

```yaml
site:
  name: jaci
stack:
  load: true
  root: /p/projetos/GROUP/USER/work/ACTUAL-STACK/spack-stack
jedi:
  install_root: /p/projetos/GROUP/USER/build/monan-jedi
environment:
  MONAN_MESH_ROOT: /p/.../meshes/...
  MONAN_PHYSICS_ROOT: /p/.../physics/...
  MONAN_BMATRIX_ROOT: /p/.../covariance/...
  MONAN_INPUT_ROOT: /p/.../external-inputs
  MONAN_GFS_ROOT: /p/.../data/gfs
  MONAN_LIBFABRIC_ROOT: /opt/cray/.../lib64
runtime:
  unload_anaconda: true
  validate_python: false
```

Illustrative paths only: **never copy a fake path**. `experiment site save`
writes exactly the real locations validated in the current terminal.

## Future experiments in fresh terminals

With the shared profile present:

```bash
experiment create /p/projetos/monan_das/$USER/work/new-date \
  --start 2026-01-29T00:00:00Z
cd /p/projetos/monan_das/$USER/work/new-date
source ./environment.sh
experiment check campaign.yaml
experiment export campaign.yaml
experiment validate workflow.yaml
experiment plan workflow.yaml
```

`experiment create` automatically reads `<workspace>/site.yaml`, copies a
resolved scientific subset into `science/site.yaml`, and generates
`environment.sh` with explicit exports of the same site roots. Inherited
`STACK_ROOT` cannot silently override the declared site. Scientific PBS
scripts continue to use the existing shared `site.py` renderer and v2
manifest; no Python is required inside compute jobs.

For a different site profile, use:

```bash
experiment create /p/path/to/new-case --start 2026-01-29T00:00:00Z \
  --site /absolute/path/to/verified/site.yaml
```

An explicit site profile must contain `site`, `stack.root` and
`jedi.install_root`; additional existing paths may be specified under
`environment`. For reproducibility, persistent root paths should be literal
and absolute rather than referencing `STACK_ROOT` from the current shell.

## Existing successful campaigns

**Do not modify or recreate** successful 2024, 2025 and 2026 experiments
to adopt the new site profile. Their outputs and provenance remain valid.
The shared profile affects only newly created experiments.

Run `python -m pytest tests/test_site_profile_persistence.py
tests/test_experiment_start.py tests/test_scientific_environment.py -q`
before testing a fresh-shell experiment.
