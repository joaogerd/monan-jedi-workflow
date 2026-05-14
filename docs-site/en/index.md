# MONAN-JEDI-WORKFLOW

**MONAN-JEDI-WORKFLOW** is a project for preparing, validating and running data assimilation experiments with **MONAN/MPAS-JEDI** on INPE HPC systems, initially targeting the **JACI** supercomputer and **3DVar-FGAT** cycles.

The project is not intended to become a monolithic workflow. It separates environment setup, data preparation, scientific configuration, validation, execution and orchestration.

## What it provides

- JACI environment loading;
- data layout bootstrap;
- external input staging;
- staged input validation;
- IODA inventory checks;
- scientific input checklist;
- MPAS-JEDI build discovery;
- JEDI YAML rendering;
- PBS job rendering.

## Recommended reading

1. [Overview](overview.md)
2. [Architecture](architecture.md)
3. [Installation and configuration](installation.md)
4. [User guide](usage.md)
5. [Cookbook / How-to](cookbook.md)
