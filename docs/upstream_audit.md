# Upstream MPAS-Workflow audit

This document records the first technical audit of the upstream repository
[`NCAR/MPAS-Workflow`](https://github.com/NCAR/MPAS-Workflow) before importing or rewriting
components for MONAN-JEDI-WORKFLOW.

The goal is not to copy the original project blindly. The goal is to identify which parts are
scientifically essential, which parts are workflow infrastructure, which parts are site-specific,
and which parts must be redesigned for INPE/JACI.

## 1. Upstream identity

The upstream project is a workflow for cycling forecast and data assimilation experiments with
MPAS-Atmosphere and JEDI-MPAS. It is orchestrated with Cylc 8 and uses YAML scenario files as the
primary user-facing configuration interface.

It is important to keep the boundary clear:

- MPAS-Workflow does **not** build MPAS-Atmosphere.
- MPAS-Workflow does **not** build JEDI-MPAS.
- MPAS-Workflow expects a previously built `mpas-bundle` or equivalent JEDI/MPAS installation.
- MPAS-Workflow generates task configuration, runtime files, Cylc suite fragments, and calls task scripts.

## 2. Upstream control flow

The core control flow is:

```text
scenario YAML
    -> initialize/**/*.py
    -> config/auto/*.csh
    -> suite.rc
    -> Cylc task graph
    -> bin/*.csh task scripts
    -> MPAS-Atmosphere / JEDI-MPAS executables
```

The upstream driver is `Run.py`. It parses a selected scenario file, initializes the scenario,
selects a suite class, and submits the Cylc suite. The generated `suite.rc` and `config/auto/*.csh`
files are temporary runtime artifacts.

## 3. Main upstream directories

| Upstream path | Role | Migration decision |
|---|---|---|
| `Run.py` | Main driver that parses scenarios and submits Cylc suites | Study and partially redesign; do not copy blindly |
| `initialize/` | Python initialization layer; maps YAML nodes to tasks, dependencies and generated files | Essential architecture reference |
| `scenarios/` | User-facing scenario YAMLs | Preserve concepts; rewrite site-specific examples |
| `scenarios/defaults/` | Resource defaults for model, observations, forecast, variational, verification, etc. | Preserve structure; split NCAR and JACI resources |
| `config/mpas/` | MPAS namelists, streams, variables and geophysical variables | Scientifically critical; preserve and document |
| `config/jedi/` | JEDI application templates and observation plugs | Scientifically critical; preserve and document |
| `bin/*.csh` | Runtime task scripts called by Cylc | Convert gradually to Bash after equivalence tests |
| `tools/*.py` | Python utilities for YAML, dates, members and file manipulation | Preserve useful utilities; audit individually |
| `env-setup/` | Site/runtime environment setup | Replace with site-specific INPE/JACI environment scripts |

## 4. Site-specific coupling observed

The upstream project contains strong NCAR/Derecho assumptions:

- `Run.py` checks `NCAR_HOST == derecho` and sets a Derecho-specific `CYLC_ENV` when needed.
- scenario defaults contain `/glade/...` paths.
- default resources are tuned around NCAR/Derecho node layout and filesystem paths.
- upstream documentation uses PBS through a Cylc platform named `pbs_cluster`.

For INPE, these assumptions must be isolated under:

```text
configs/sites/ncar/
configs/sites/jaci/
```

No NCAR path should be used directly in an INPE experiment configuration.

## 5. Scientific configuration that must not be removed casually

The following categories are scientifically important and must be preserved, studied and ported carefully:

- MPAS model mesh configuration;
- MPAS namelist templates;
- MPAS stream templates;
- analysis and state variable lists;
- JEDI variational application YAMLs;
- JEDI HofX YAMLs;
- observation plug templates;
- SABER/BUMP covariance configuration;
- localization and covariance resources;
- first background and external analysis resources;
- observation resources and IODA naming conventions.

## 6. First MONAN migration rule

For this repository, upstream material should be imported in three levels:

1. **Reference documentation**: describe the role of each upstream component.
2. **Preserved templates**: copy only scientific templates that are needed for 3DVar-FGAT, with license attribution and clear provenance.
3. **Rewritten runtime layer**: replace C-shell task wrappers and site-specific assumptions with Bash/Python abstractions appropriate for INPE/JACI.

## 7. Initial conclusion

The upstream workflow is mature in terms of scientific workflow concepts, but it is not a clean
starting point for an INPE production workflow without refactoring. The correct strategy is to
retain the scientific configuration model and the Cylc-based orchestration idea, while gradually
rewriting the runtime interface, environment handling, site configuration and experiment layout.
