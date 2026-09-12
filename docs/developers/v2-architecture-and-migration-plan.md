# MONAN-JEDI-Workflow V2 Architecture and Migration Plan

## Status

Draft foundation document. This document defines the target architecture and the migration order for the next major version of MONAN-JEDI-Workflow.

## Purpose

MONAN-JEDI-Workflow shall become the single operational and research-facing framework for running atmospheric data-assimilation experiments based on MONAN, MPAS, JEDI, IODA, and SABER/BUMP.

The framework must support:

- observation conversion and quality-control preparation;
- MPAS static-data, initialization, forecast, and restart workflows;
- JEDI applications such as 3D-Var, 3D-Var FGAT, and future 4D-Var workflows;
- static background-error covariance generation through NMC, BFLOW, VBAL, HDIAG, NICAS, single-observation, and DIRAC stages;
- reproducible research runs on JACI;
- portable workflow definitions that can be rendered for simpleWorkflow, ecFlow, Cylc, or a local test runner.

## Architectural Rules

1. Scientific capabilities belong to **components**.
2. Scientific dependency graphs belong to **workflows**.
3. Scheduler-specific execution belongs to **orchestration adapters**.
4. Machine- and site-specific behavior belongs to **platforms**.
5. Every executable stage must be runnable both directly through the CLI and through an orchestration adapter.
6. A stage must never infer scientific inputs from an undocumented current directory, implicit shell state, or an undeclared environment variable.
7. User-facing documentation, CLI help, error messages, configuration keys, and public docstrings must be written in English.

## Target Layout

```text
monan-jedi-workflow/
├── src/monan_jedi_workflow/
│   ├── core/
│   ├── platforms/
│   ├── components/
│   │   ├── model/mpas/
│   │   ├── observations/
│   │   ├── assimilation/jedi/
│   │   └── bmatrix/
│   ├── workflows/
│   │   ├── das_cycle/
│   │   └── bmatrix/
│   └── orchestration/
│       ├── simpleworkflow/
│       ├── ecflow/
│       ├── cylc/
│       └── local/
├── configs/
│   ├── cases/
│   ├── sites/
│   ├── profiles/
│   ├── science/
│   └── workflows/
├── tests/
├── docs/
└── examples/
```

## Core Services

The `core` package must provide reusable, domain-neutral services:

- configuration loading, resolution, and validation;
- artifact definitions, integrity checks, and lifecycle management;
- NetCDF format policies and structural validation;
- run manifests and provenance;
- persistent stage state and idempotency;
- scheduler-independent stage contracts;
- workflow specifications and dependency validation;
- validation reports.

The core package must not contain MPAS, JEDI, IODA, SABER, or site-specific scientific logic.

## Component Responsibilities

### Model / MPAS

The MPAS component owns static-data generation, initialization, forecast preparation, runtime rendering, restart discovery, and model-product validation.

### Observations

The observations component owns source-data preparation, Obs2IODA conversion, IODA product validation, and observation-specific quality-control workflows.

### Assimilation / JEDI

The JEDI component owns geometry, background staging, observation staging, rendered JEDI application configuration, application execution, and diagnostics.

### Background-Error Covariance Matrix

The B-matrix component owns NMC-pair manifests, BFLOW preprocessing, VBAL calibration, HDIAG, NICAS, single-observation diagnostics, and DIRAC diagnostics.

## Workflow Responsibilities

A workflow composes components into a scientific dependency graph.

- `das_cycle` composes observations, model background, JEDI assimilation, analysis, forecast, and verification.
- `bmatrix` composes NMC pairs, BFLOW, VBAL, HDIAG, NICAS, single-observation, and DIRAC stages.

Workflows may not duplicate the scientific implementation of their components.

## Orchestration Responsibilities

A workflow specification must be independent of the scheduler. The same graph must be usable by:

- `simpleworkflow` for research development and lightweight DAG execution;
- `ecflow` for operational deployment;
- `cylc` for partner deployments;
- `local` for test fixtures and debugging.

An adapter may render task definitions and scheduler scripts, but must invoke the same stage CLI contract as direct execution.

## Configuration Model

A normal user edits one case file. Advanced configuration is composed from site, profile, science, and workflow configuration files.

```text
case.yaml
  + site.yaml
  + profile.yaml
  + science.yaml
  + workflow.yaml
  = resolved-config.yaml
```

The resolved configuration must be saved in every run workspace.

## Artifact and NetCDF Policy

Every artifact consumed by another stage must have an explicit contract:

- producer stage;
- consumer stage;
- file format;
- required variables, dimensions, and attributes;
- time convention;
- checksum policy;
- validation routine.

NetCDF compatibility is a first-class contract. A stage must validate the output format required by its consumer before submission, not after a failed MPI job.

## Migration Strategy

The current `main` branch remains the V1 reference implementation. Existing repositories and branches are evidence sources, not templates to copy without review.

Migration occurs one validated capability at a time:

1. V2 foundation and quality standards.
2. NMC pairs V1.
3. BFLOW V1.
4. VBAL V1.
5. HDIAG V1.
6. NICAS V1.
7. Single-observation V1.
8. DIRAC V1.
9. Observation-conversion and DAS-cycle migration.

A later stage must not begin implementation until the immediately preceding stage meets the project definition of done.

## Initial Milestones

### Milestone A: Foundation

Deliver the core stage contract, workflow specification, local adapter, simpleWorkflow adapter contract, configuration resolution, artifact model, state model, documentation standards, and CI quality gates.

### Milestone B: NMC Pairs V1

Reimplement the validated NMC-pair capability using the V2 foundation. The output is the official manifest consumed by BFLOW.

### Milestone C: BFLOW V1

Migrate the validated scientific algorithm only after quantitative comparison against the reference implementation.

### Milestone D: VBAL V1 and Later B-Matrix Stages

Migrate one stage at a time with real JACI validation and complete artifact contracts.

## Explicit Non-Goals for Milestone A

- Rewriting MPAS, JEDI, SABER, ESMF, or scheduler software in Python.
- Supporting all current legacy commands in V2.
- Migrating all components before the first end-to-end validated B-matrix product.
- Treating a successful process exit code as scientific validation.
