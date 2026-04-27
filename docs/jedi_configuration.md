# JEDI Configuration

The original workflow stores JEDI application templates in:

```text
config/jedi/applications/*.yaml
config/jedi/ObsPlugs/variational/*.yaml
config/jedi/ObsPlugs/hofx/*.yaml
```

`PrepJEDI.csh` populates these templates, especially the `observers` section.

## 3DVar and 3DVar-FGAT

The inspected upstream tree has a `config/jedi/applications/3dvar.yaml` template but no confirmed
`3dfgat.yaml` file. The first MONAN 3DVar-FGAT path should therefore derive from the validated
3DVar variational workflow and document every JEDI-specific change.

Initial policy:

- use offline IODA conventional observations;
- deterministic background;
- static SABER/BUMP covariance;
- no VarBC in the first smoke test;
- one cycle before 24h cycling.
