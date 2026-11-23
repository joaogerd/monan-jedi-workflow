# MPAS-JEDI 3DVar/FGAT — reference recipe

This is the **240 km / 55-level reference case** (two 6-hour analyses).
It uses WPS, MPAS initialization, Obs2IODA conventional and GNSS-RO
conversion, JEDI 3DVar/FGAT analysis and MPAS forecasts.

The scientific files are currently retained unchanged in
`monan_jedi_workflow/catalog/reference-20250901` to preserve the tested baseline.
The descriptor in `recipe.yaml` contains defaults and supported resolution
profiles. It is not a claim that any arbitrary mesh is currently supported.

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
