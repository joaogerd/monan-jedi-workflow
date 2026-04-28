# Observer rendering

This document describes the first MONAN-side replacement for the observer assembly behavior that
is handled by upstream `PrepJEDI.csh`.

The goal is to make the observer block explicit, testable and independent of hidden C-shell
substitution.

## Current status

This implementation is structural only. The included observer plugs are skeletons for renderer
development and are not yet scientifically validated JEDI-MPAS observer definitions.

Initial plugs:

```text
configs/jedi/obs_plugs/variational/aircraft.yaml
configs/jedi/obs_plugs/variational/sondes.yaml
configs/jedi/obs_plugs/variational/sfc.yaml
```

Experiment observer manifest:

```text
configs/experiments/3dvar_fgat/observers.yaml
```

Renderer:

```text
tools/render_observers.py
```

## Workflow

The observer rendering workflow is:

```text
observers.yaml manifest
    -> selected obs_plug templates
    -> tools/render_observers.py
    -> build/rendered/observers.yaml
    -> injected into render context as jedi.observers
    -> tools/render_template.py
    -> build/rendered/3dvar_fgat.yaml
```

The high-level wrapper is:

```bash
scripts/run/render_3dvar_fgat.sh
```

## Run

```bash
scripts/run/render_3dvar_fgat.sh
```

This generates:

```text
build/rendered/observers.yaml
build/rendered/render_context.with_observers.yaml
build/rendered/3dvar_fgat.yaml
```

## Manifest format

```yaml
observers:
  - name: aircraft
    template: configs/jedi/obs_plugs/variational/aircraft.yaml
    enabled: true
```

Disabled observers are skipped:

```yaml
observers:
  - name: aircraft
    template: configs/jedi/obs_plugs/variational/aircraft.yaml
    enabled: false
```

## Template format

Each observer plug is a YAML list fragment. This is intentional because the final `observers`
section in JEDI is also a list.

Example:

```yaml
- obs space:
    name: aircraft
    obsdatain:
      engine:
        type: H5File
        obsfile: {{obs.aircraft.file}}
```

## Limitations

This layer does not yet:

- validate UFO observer names;
- validate simulated variables;
- validate IODA file schema;
- implement bias correction;
- implement QC filters;
- support radiance observers;
- reproduce all upstream ObsPlug behavior;
- guarantee scientific correctness.

## Next development steps

1. Import or reconstruct validated conventional observation plugs.
2. Add schema checks for rendered observer YAML.
3. Add support for observer-specific filters.
4. Add VarBC/radiance observers only after conventional-only 3DVar works.
5. Compare rendered YAML against a known-good upstream MPAS-JEDI YAML.
