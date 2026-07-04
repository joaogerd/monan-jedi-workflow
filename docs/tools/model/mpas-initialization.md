# MPAS Initialization

## Status

Draft V2 component. YAML-to-stage compilation, explicit runtime staging, local execution, JACI PBS rendering/submission/wait, artifact validation, optional structural NetCDF contracts, and NMC campaign planning are implemented and covered by local tests. When a campaign declares `model.wps`, the planner provides one explicit WPS `FILE:` forcing artifact per initialization. The first real JACI canary established that WPS ungrib succeeds; MPAS initialization is being validated incrementally with explicit mesh, forcing, and geographical-data preflight contracts.

## Purpose

`mpas-initialization` creates and validates one initial MPAS state at a specified cycle time. It is the producer of initial conditions for forecast stages used by data-assimilation and NMC B-matrix campaigns.

## Scientific Context

An MPAS forecast must start from a state consistent with the selected mesh, static fields, forcing, geographical data, and cycle time. In the global configuration used by the NMC campaign, `init_atmosphere` reads three distinct inputs:

- the MPAS mesh NetCDF file through the `input` stream, for example `x1.10242.grid.nc`;
- the WPS `FILE:YYYY-MM-DD_HH` intermediate through `config_met_prefix = 'FILE'` and `config_fg_interval`;
- a local WPS_GEOG tree through `config_geog_data_path`, with the dataset directories requested by the selected MPAS static interpolation settings.

The WPS intermediate is not a NetCDF mesh and must never replace the mesh stream filename. An installed MPAS template can carry site-specific NCAR geography paths; V2 rewrites only the declared namelist setting and requires local input indexes before submitting PBS.

## When to Use the Tool

Use this component before any V2 MPAS forecast that depends on an initial state produced by the same workflow. Do not use it to convert observations or run JEDI assimilation.

## Inputs

- a cycle time;
- `model.mpas.initialization_products` with an absolute initial-state root and path template;
- an explicit `*.grid.nc` mesh link for MPAS stream bootstrap;
- static geography, graph, partition, and other model inputs declared as explicit links or templates;
- an upstream WPS `FILE:` artifact when the NMC campaign declares `model.wps`;
- `geog_data_path` and `geog_required_datasets` when WPS forcing is used;
- `model.mpas.initialization` with an explicit command, run directory, optional environment, links, templates, and validation rules.

## Outputs

The stage publishes one initial MPAS state file. Its path is defined by `state_template` and becomes the explicit `{initial_state}` input of forecast staging.

## Artifact Contract

| Artifact | Producer | Consumer | Current validation |
| --- | --- | --- | --- |
| MPAS `*.grid.nc` mesh | Static mesh source | MPAS initialization stream `input` | Declared link and stream filename |
| WPS `FILE:` forcing | WPS ungrib | MPAS initialization namelist path | Declared producer, separate explicit link, existence/non-empty |
| WPS_GEOG directories | Site data installation | MPAS static interpolation | Declared absolute root and required `dataset/index` files |
| Initial MPAS state | MPAS initialization | MPAS forecast | Exists/non-empty; optional NetCDF format/schema/mesh/time contract |
| Initialization log | MPAS initialization | Validation/orchestration | Optional markers |
| PBS script | JACI platform adapter | PBS | Explicit argv/resources |

## YAML Configuration

A complete component example is at `examples/v2/model/mpas_initialization.yaml.example`; the full WPS-to-NMC workflow example is at `examples/v2/bmatrix/nmc_campaign.yaml.example`.

Supported template tokens are `workspace`, `cycle_time`, `init_time`, `init_yyyymmddhh`, `valid_time`, `valid_yyyymmddhh`, `mpas_valid_file_time`, `wps_time`, `lead_hours`, `lead_hours_03d`, `state`, and `run_dir`.

The campaign binds WPS forcing and local geographical data through:

```yaml
model:
  mpas:
    initialization:
      wps_input:
        target: "FILE:{wps_time}"
      geog_data_path: /absolute/path/to/WPS_GEOG/mpas_lowres_compat
      geog_required_datasets:
        - topo_gmted2010_30s
        - soiltype_top_30s
      links:
        - source: /absolute/path/to/x1.10242.grid.nc
          target: x1.10242.grid.nc
```

`wps_input.target` creates the separate WPS forcing link. The initialization renderer keeps the stream `input` bound to the declared `*.grid.nc` mesh link. Before PBS submission, the stage requires each declared `${geog_data_path}/${dataset}/index` file and then writes `config_geog_data_path` into `namelist.init_atmosphere`.

Optional structural checks live under `model.mpas.artifact_validation.initialization_state`; see `examples/v2/science/mpas_artifact_validation.yaml.example`.

## Parameters

| Parameter | Effect |
| --- | --- |
| `cycle_time` | Initialization time. |
| `state_template` | Expected initial-state path. |
| `run_dir` | Initialization working directory. |
| `argv` | Exact executable arguments. |
| `links` | Inputs staged as idempotent symbolic links. |
| `templates` | Input files rendered from explicit context. |
| `wps_input.target` | Separate target filename for the upstream WPS artifact; it must begin with `FILE:`. |
| `geog_data_path` | Absolute local WPS_GEOG root written to `config_geog_data_path` for WPS-backed initialization. |
| `geog_required_datasets` | Dataset directory names that must each contain an `index` file before PBS submission. |
| `required_log_markers` | Completion markers checked in the selected log. |
| `artifact_validation` | Optional NetCDF format, schema, metadata, and time checks. |

## Dependencies

- Python 3.10 or newer;
- netCDF4 Python bindings;
- MPAS initialization executable and input data;
- WPS `ungrib` and forcing files when `model.wps` is enabled;
- a site-local WPS_GEOG installation when WPS forcing is enabled;
- PBS commands when running through the JACI backend.

## CLI Usage

The public workflow command is:

```bash
monan-jedi-workflow-v2 nmc-campaign \
  --config examples/v2/bmatrix/nmc_campaign.yaml.example \
  --workspace /path/to/workspace \
  --dry-run
```

A standalone initialization CLI is not exposed yet; the campaign command invokes the same initialization stage contract.

## simpleWorkflow Usage

Render the campaign with `nmc-campaign --render-simpleworkflow`; each initialization task depends on its matching WPS task when WPS is configured.

## ecFlow and Cylc Integration Contract

The orchestration task invokes the same explicit request. Queue, module prelude, launcher, and resource settings remain platform configuration. The WPS dependency must remain explicit: `wps_ungrib(cycle) -> mpas_init(cycle)`.

## Validation

The stage validates link/template sources before execution, then requires the initial-state file, optional log markers, and configured NetCDF format/schema/metadata/time checks after backend completion. Scheduler completion alone is not scientific success. A WPS-backed preflight verifies the `FILE:` forcing link, the rendered MPAS `input` stream, the local `config_geog_data_path`, and all declared geographical `index` files.

## Restart and Idempotency Behavior

Matching symbolic links are reused. Regular run-directory targets are not overwritten by staging. The workflow runner revalidates declared outputs before reusing a previous successful state.

## Limitations

- The first MPAS init canary established that the mesh stream and WPS forcing must be treated as different inputs; both are now checked in preflight.
- The local WPS_GEOG package must be appropriate for the selected static interpolation settings; low-resolution alias trees are suitable for functional smoke tests, not necessarily for production-quality static fields.
- The exact production baseline variables, mesh metadata, static geography, forcing coverage, and time conventions still need confirmation.
- No standalone public V2 CLI yet.
- No scientific comparison against an accepted MPAS initialization baseline yet.

## FAQ

### Why is initialization separate from forecast?

The stages publish different scientific products, have different validation contracts, and may have different upstream dependencies. Keeping them separate makes the DAG explicit and allows controlled retries.

### Why does initialization receive a WPS FILE artifact rather than metgrid output?

The selected MPAS global initialization configuration reads the WPS intermediate directly. The workflow should model the artifact actually consumed instead of creating an unused metgrid stage.

### Why does the MPAS input stream not point to WPS FILE?

The input stream bootstraps MPAS from its mesh NetCDF file. WPS `FILE:` is a separate intermediate forcing format and is selected by the initialization namelist, not by the mesh stream.

### Why must geographical data be declared explicitly?

Installed MPAS templates may refer to paths from the build site. A declared `geog_data_path` makes the required site input explicit, portable across environments, and testable before an MPI submission.

### Does a successful initialization guarantee a valid forecast?

No. The forecast stage still validates its own restart/state outputs and has its own runtime contract.

## References

- MPAS-Atmosphere documentation.
- WPS User's Guide.
- `docs/developers/v2-architecture-and-migration-plan.md`.
