# Observer plug contract

This document defines the current MONAN-JEDI-WORKFLOW observer plug contract.

The upstream MPAS-Workflow assembles JEDI observer YAML fragments during `PrepJEDI.csh`. That
process also depends on observation file availability, application type, bias correction settings,
anchors and filters.

The current MONAN implementation is intentionally smaller. It defines the structural contract that
must be satisfied before deeper scientific validation is added.

## Files

Observer manifest:

```text
configs/experiments/3dvar_fgat/observers.yaml
```

Observer plug templates:

```text
configs/jedi/obs_plugs/variational/*.yaml
```

Observer metadata registry:

```text
configs/jedi/obs_plugs/variational/metadata.yaml
```

Manifest checker:

```text
tools/check_observer_manifest.py
```

Metadata checker:

```text
tools/check_observer_metadata.py
```

## Manifest contract

Each observer entry must define:

```yaml
observers:
  - name: aircraft
    template: configs/jedi/obs_plugs/variational/aircraft.yaml
    enabled: true
```

Rules:

- `name` must be unique;
- `template` must point to an existing file;
- `enabled` must be boolean;
- disabled observers are skipped by the renderer;
- the observer name must appear in the template text.

## Metadata contract

Every observer used in the experiment manifest must also appear in the metadata registry.

Each metadata entry must define:

```yaml
observer_plugs:
  aircraft:
    template: configs/jedi/obs_plugs/variational/aircraft.yaml
    status: structural_skeleton
    category: conventional
    expected_ioda_group: aircraft
    requires_bias_correction: false
    validated_on_jaci: false
    notes: Placeholder observer for rendering tests.
```

The `status` field is deliberately explicit. Current allowed values are descriptive, not enforced:

- `structural_skeleton`;
- `candidate_for_validation`;
- `validated_on_jaci`.

## Current structural plugs

Current plugs are structural skeletons only:

- `aircraft`;
- `sondes`;
- `sfc`.

They are useful for testing the rendering pipeline, but they are not yet scientifically validated
UFO/JEDI observer configurations.

## What still needs scientific validation

Before real use, each observer plug must be checked for:

- correct UFO operator name;
- correct simulated variables;
- correct IODA input schema;
- correct feedback output behavior;
- QC filters;
- observation error settings;
- bias correction requirements;
- compatibility with the selected MPAS-JEDI bundle.

## Upstream behavior to reproduce later

The upstream `PrepJEDI.csh` performs additional observer-related tasks that are not yet reproduced:

- links IODA files into runtime input directories;
- skips observers when files are missing;
- combines application-specific and common YAML anchors;
- switches between base, bias and filter plug subdirectories;
- handles bias correction files;
- performs date/time substitutions;
- inserts final observer YAML into the application template.

MONAN-JEDI-WORKFLOW currently reproduces only the last part in a simplified form:

```text
observer manifest + plug templates -> rendered observers -> JEDI YAML
```
