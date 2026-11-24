# MPAS-JEDI 3DVar/FGAT — reference recipe

This is the **240 km / 55-level reference case** (two 6-hour analyses).
It uses WPS, MPAS initialization, Obs2IODA conventional and GNSS-RO
conversion, JEDI 3DVar/FGAT analysis and MPAS forecasts.

The recipe is self-contained: its scientific YAMLs, templates, runners and
runtime skeleton live in `science/`, next to `recipe.yaml` and this README.
The legacy `catalog:reference-20250901/...` lookup remains supported as a
compatibility alias, but the duplicate scientific files are no longer stored
under `catalog/`. All new experiments use this recipe directory.
The descriptor in `recipe.yaml` defines the supported defaults and profiles.
It is not a claim that arbitrary meshes work automatically.

## First run

```bash
experiment create "$CASE" --recipe mpas-jedi-3dvar \
  --workspace "$WORKSPACE" --start 2026-01-30T00:00:00Z
cd "$CASE"
source ./environment.sh
experiment check-inputs .
experiment check campaign.yaml
experiment export campaign.yaml
experiment validate workflow.yaml
experiment plan workflow.yaml
experiment run workflow.yaml --ui plain
```

This recipe depends on the MPAS-JEDI scientific binaries, matching meshes,
partition files, vertical grids, covariance B, physical tables and date-specific
GFS/observations. Installation of the Python package does not install them.

### Parameters

- `--resolution`: resolution profile (240km currently bundled; additional
  profiles must provide validated assets and science templates)
- `--levels`: number of vertical levels (55 in reference; custom values require
  corresponding grids and compatible configuration)
- `--cycle`, `--duration`: requested cycle and period; the MPAS reference
  currently provides a six-hour forecast/FGAT contract
- `--mode`: cold only; warm restart remains unimplemented
- `--observations`: conventional and GNSS-RO reference converters
- `--config`: YAML with overrides (explicit CLI values take precedence)

**Scientific validity:** a change of mesh, vertical levels, background-error
covariance, temporal interval or observation operators must not silently reuse
the 240 km reference data. The create command must fail closed until the
corresponding resource contract is supplied and validated.

The packaged reference is a regression baseline, not a universal model setup.

### Adding a new resolution to this recipe

Do not change the 240 km reference files. Supply a complete, tested
resolution-specific scientific configuration tree, for example
`profiles/60km/science/`, with its own MPAS initialization, partition,
invariant, JEDI, B-matrix and Obs2IODA contracts. Add an entry to
`resolution_profiles`:

```yaml
60km:
  mesh: /shared/mesh-60km
  bmatrix: /shared/covariance-60km
  mesh_id: x1.CELLS
  levels: 55
  observations: [conv, gpsro]
  science_source: profiles/60km/science
```

Paths and identifiers here are **placeholders**, not verified JACI resources.
The source must contain the same mandatory scientific entrypoint YAML files as
the reference. A profile selects the whole science configuration tree; it does
not apply blind string substitutions to 240 km files.

A profile is an explicit declaration of compatibility, not a substitute for
a scientific validation run. The default distributed recipe includes only
the validated-reference 240 km descriptor.
