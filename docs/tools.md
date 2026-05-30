# MONAN-JEDI workflow tools

This page is the index for the command-line tools available under [`tools/`](../tools/). These scripts support the MONAN-JEDI workflow by preparing data layouts, auditing input registries, staging scientific files, rendering templates, assembling observer configuration, validating rendered products, checking MPAS-JEDI builds, preparing runtime directories, and building the variational run command.

The tools are small on purpose. Most of them are pre-flight checks or operational helpers. They help users detect missing files, unresolved variables, inconsistent YAML manifests, incomplete rendered products, or invalid runtime layouts before submitting jobs on HPC systems.

Use this documentation when you need to know what a tool does, how to run it, which inputs it expects, which options it accepts, and how it relates to the rest of the workflow.

## Recommended reading order

1. [`bootstrap_data_layout.py`](tools/01-bootstrap-data-layout.md)
2. [`audit_input_sources.py`](tools/02-audit-input-sources.md)
3. [`sync_input_sources.py`](tools/03-sync-input-sources.md)
4. [`check_external_input_root.py`](tools/04-check-external-input-root.md)
5. [`check_input_consistency.py`](tools/05-check-input-consistency.md)
6. [`stage_inputs.py`](tools/06-stage-inputs.md)
7. [`validate_staged_inputs.py`](tools/07-validate-staged-inputs.md)
8. [`validate_file_formats.py`](tools/08-validate-file-formats.md)
9. [`audit_scientific_inputs.py`](tools/09-audit-scientific-inputs.md)
10. [`check_ioda_inventory.py`](tools/10-check-ioda-inventory.md)
11. [`validate_ioda_structure.py`](tools/11-validate-ioda-structure.md)
12. [`check_observer_manifest.py`](tools/12-check-observer-manifest.md)
13. [`check_observer_metadata.py`](tools/13-check-observer-metadata.md)
14. [`render_observers.py`](tools/14-render-observers.md)
15. [`validate_jedi_observer_config.py`](tools/15-validate-jedi-observer-config.md)
16. [`check_placeholders.py`](tools/16-check-placeholders.md)
17. [`render_template.py`](tools/17-render-template.md)
18. [`validate_experiment.py`](tools/18-validate-experiment.md)
19. [`validate_fgat_window.py`](tools/19-validate-fgat-window.md)
20. [`validate_mpas_background.py`](tools/20-validate-mpas-background.md)
21. [`validate_saber_inputs.py`](tools/21-validate-saber-inputs.md)
22. [`find_mpas_jedi_build.py`](tools/22-find-mpas-jedi-build.md)
23. [`check_mpas_jedi_build.py`](tools/23-check-mpas-jedi-build.md)
24. [`prepare_runtime.py`](tools/24-prepare-runtime.md)
25. [`run_variational.py`](tools/25-run-variational.md)
26. [`create_github_repo_manual.sh`](tools/26-create-github-repo-manual.md)

## Practical use

During initial setup, start with the data-layout and input-source tools. Before rendering or running JEDI, use the consistency and validation tools. After rendering, check observers, templates, FGAT timing, MPAS background, SABER inputs, and experiment structure. Before execution, check the MPAS-JEDI build, prepare the runtime directory, and inspect the variational command.

Most tools return `0` when checks pass and `2` when required validation fails. Non-strict modes usually print warnings instead of failing.
