# Adaptation and extension

## What can be adapted

The system supports controlled adaptation of HPC sites, queues, paths, experiments, JEDI observers, MONAN forecast scripts and future orchestration layers.

## What should remain stable

The interfaces between layers should remain stable:

- `configs/sites/` defines environment and paths.
- `configs/experiments/` defines experiment choices.
- `scripts/setup/` prepares and validates.
- `scripts/run/` executes high-level steps.
- `tools/` contains reusable logic.
- `jobs/` contains submission templates.

## Best practices

Keep site paths out of scientific templates. Avoid embedding scientific logic in PBS or orchestration files. Keep examples versioned and real data out of Git. Use wrappers to integrate external MONAN forecast scripts.

## Current limitations

The workflow does not yet fully implement real MONAN/MPAS forecast execution, automatic weekly cycling, internal NetCDF/HDF5 content validation, scientifically validated JEDI observers or an ecFlow layer.
