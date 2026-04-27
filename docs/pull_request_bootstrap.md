# Bootstrap MONAN-JEDI-WORKFLOW for JACI 3DVar-FGAT

## Summary

This PR creates the initial MONAN-oriented workflow scaffold derived conceptually from NCAR/MPAS-Workflow.

## Main changes

- Adds documentation for architecture, configuration, MPAS, JEDI, JACI setup and migration notes.
- Adds a clean directory structure separating site, experiment, MPAS, JEDI and workflow layers.
- Adds JACI site environment example and PBS smoke-test job.
- Adds Bash helper scripts with `set -euo pipefail`.
- Adds a conservative 3DVar-FGAT experiment skeleton.
- Adds a technical roadmap for incremental migration.

## Notes

This PR does not claim full scientific execution yet. It establishes a safe, reviewable base for
porting the original C-shell/Cylc task model to a MONAN/JACI-oriented implementation.
