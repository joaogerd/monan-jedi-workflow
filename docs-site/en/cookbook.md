# Cookbook / How-to

## Configure a new HPC site

1. Create `configs/sites/<site>/`.
2. Add `site.env.example`.
3. Define modules, queue, account, paths and MPI launcher.
4. Add site-specific environment loading if needed.
5. Validate with:

```bash
bash scripts/setup/check_runtime.sh configs/sites/<site>/site.env
```

Do not put site-specific absolute paths inside scientific JEDI or MONAN templates.

## Adapt an existing configuration

Copy the example before editing:

```bash
cp configs/experiments/3dvar_fgat/input_sources.jaci.example.yaml \
   configs/experiments/3dvar_fgat/input_sources.jaci.yaml
```

Edit local copies and keep examples versioned.

## Add a new observer

1. Add a template under `configs/jedi/obs_plugs/variational/`.
2. Register it in `configs/experiments/3dvar_fgat/observers.yaml`.
3. Add metadata in `configs/jedi/obs_plugs/variational/metadata.yaml`.
4. Update the IODA inventory.
5. Run observer validation tools.

## Test changes

Always run:

```bash
bash tests/smoke_check.sh
```

Use stricter checks only when real data and executables are available.

## Debug missing MPAS-JEDI build

```bash
bash scripts/setup/find_mpas_jedi_build.sh --max-depth 7 ${MONAN_JACI_WORKSPACE}/projects
```

Then update `MPAS_BUNDLE_BUILD` in `site.env`.
