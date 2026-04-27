# MPAS Configuration

The original MPAS-Workflow documentation identifies `config/mpas/` as the location for static
MPAS-Atmosphere controls, including:

- `geovars.yaml`;
- `variables.csh`;
- application-specific `namelist.atmosphere`, `streams.atmosphere`, and stream lists.

The MONAN layout separates:

```text
configs/mpas/
├── geovars.yaml
├── variables.yaml
├── namelist.atmosphere.template
└── streams.atmosphere.template
```

A first 3DVar-FGAT test needs MPAS mesh, static/invariant file, graph partition files, model
timestep, physics suite, forecast output interval, DA stream availability and background state
filenames/dates.
