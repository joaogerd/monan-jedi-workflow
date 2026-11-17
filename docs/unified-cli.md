# MONAN Workflow — one CLI, independent scientific domains

The user-facing program is **`monan-workflow`**. The internal Python
package and installed scientific components can remain separately versioned
and tested. This is a CLI-level change, not a merger of the scientific apps
or the design of a new scheduler.

## Public commands

```text
monan-workflow
├── experiment
│   ├── create  (alias: start)
│   ├── check
│   ├── export
│   ├── validate
│   ├── plan
│   ├── run
│   ├── status
│   ├── suggest-dates
│   └── check-inputs
├── wps
│   ├── prepare
│   ├── run
│   └── validate
├── obs
│   ├── acquire
│   └── convert
├── mpas
│   ├── init
│   ├── prepare
│   ├── run
│   └── validate
├── jedi
├── diagnostic
└── diagnose
```

OBS/MPAS/JEDI/diagnostic domain commands retain the existing
`prepare|run|validate|status|inspect|check` lifecycle, with nested
`obs acquire|convert` and `mpas init`.

`diagnostic` performs **scientific** cost/departure diagnostics (existing
domain application). `diagnose` provides **operational** log/PBS diagnosis
(read-only). These are intentionally distinct.

### New user cold-start example

```bash
monan-workflow experiment create \
  /p/projetos/monan_das/$USER/work/independent-case \
  --start 2024-02-29T00:00:00Z --mode cold

cd /p/projetos/monan_das/$USER/work/independent-case
source ./environment.sh

monan-workflow experiment check campaign.yaml
monan-workflow experiment export campaign.yaml
monan-workflow experiment validate workflow.yaml
monan-workflow experiment plan workflow.yaml
monan-workflow experiment run workflow.yaml --ui plain
monan-workflow diagnose . --verbose
```

The generator copies the scientific recipe, resolves all temporal
references from `--start`, writes `science/site.yaml`, and leaves the
created directory immutable until each stage's normal lifecycle.

**Warm start is not yet implemented**. Passing `--mode warm` explicitly
fails and creates no files rather than silently falling back to cold start.

The installed simpleWorkflow executable `swf` remains the engine under
`experiment validate|plan|run|status`, invoked as a child process. PBS
submission remains with native MPAS/JEDI/WPS/OBS apps. `monan-workflow`
does not create another orchestrator.

### Migration

Existing scientific experiment directories and old executables
(`monan-jedi-workflow`, `obs`, `jedi`, `mpas`, `campaign`) remain
available for backward compatibility during transition.

**Newly exported** workflows use only the `monan-workflow` executable
for all 24 scientific stage tasks.

The Python import namespace remains `monan_jedi_workflow` for now to
avoid breaking installed scripts and tests; distribution renaming and
retiring aliases should happen in a later explicit release, after JACI
validation.

Run `python -m pip install -e .` or your site's package installation
procedure after pulling the new source: changing `[project.scripts]` in
`pyproject.toml` alone does not guarantee an existing installed environment
will discover the new `monan-workflow` command.

## Validation

```bash
python -m pytest tests/test_unified_cli.py tests/test_experiment_start.py -q
command -v monan-workflow
monan-workflow --help
```

Do not re-export over an existing `workflow.yaml`: the campaign exporter
intentionally refuses to overwrite it. Use a new case directory or a new
export path.
