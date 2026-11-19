# MONAN-JEDI Workflow — direct commands

**The repository/distribution remains `monan-jedi-workflow`.** Installing it provides
seven public executables directly on `PATH`:

| Command | Purpose |
| --- | --- |
| `experiment` | Create, check, export, plan, run and inspect the campaign |
| `wps` | Acquire meteorological GFS inputs and run WPS |
| `obs` | Acquire, convert and validate observation inputs |
| `mpas` | Initialize MPAS and run forecast cycles |
| `jedi` | Run variational data assimilation |
| `diagnostic` | Scientific diagnostics (cost function and departures) |
| `diagnose` | Operational logs, PBS jobs and fault analysis |

There is **no public `monan-workflow` executable or required prefix**.

## Example

```bash
experiment create /p/projetos/monan_das/$USER/work/date-test \
  --start 2024-02-29T00:00:00Z --mode cold

cd /p/projetos/monan_das/$USER/work/date-test
source ./environment.sh
experiment check campaign.yaml
experiment export campaign.yaml
experiment validate workflow.yaml
experiment plan workflow.yaml
experiment run workflow.yaml --ui plain

wps prepare science/initialization --cycle 2024-02-28T18:00:00Z
obs convert status experiment.yaml --cycle 2024-02-29T00:00:00Z
jedi status experiment.yaml --cycle 2024-02-29T00:00:00Z
mpas init status init.yaml --cycle 2024-02-28T18:00:00Z
diagnose . --verbose
```

`experiment` delegates graph execution to the installed `simpleWorkflow`
engine. Domain applications own their native scientific PBS submissions.
The exported workflow tasks invoke **direct domain commands** (`wps`,
`obs`, `mpas`, `jedi`, or `diagnostic`) and never prepend a wrapper command.

The `warm` mode currently refuses startup rather than silently defaulting
to cold start: scientific warm start validation remains to be implemented.
Automatic GFS acquisition is implemented for a configured provider;
historical raw observations require verified source configuration.

## Compatibility

Old experiment configurations and previous executables
(`campaign`, `diagnostics`, `monan-jedi-workflow`) are temporarily retained
so existing workflows keep working. They are **legacy compatibility aliases**,
not the documented user interface.

Existing exported workflows must not be overwritten. New workflows use
the direct commands. To register the new console scripts in a development
installation, run `python -m pip install -e .` in the repository and
then `command -v experiment wps obs mpas jedi diagnostic diagnose`.

Validate with:

```bash
python -m pytest tests/test_unified_cli.py tests/test_experiment_start.py -q
```
