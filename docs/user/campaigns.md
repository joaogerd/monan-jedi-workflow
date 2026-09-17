# Running a campaign

The normal user interface is one campaign YAML plus one command. Researchers do not need to remember the individual JEDI, MPAS and Obs2IODA stage commands.

After entering the standard MONAN-JEDI environment on JACI, the validated three-day M3 experiment is checked or started directly with:

```bash
monan-jedi-workflow campaign check \
  examples/campaigns/m3-3days-20180415.yaml

monan-jedi-workflow campaign run \
  examples/campaigns/m3-3days-20180415.yaml
```

There is no extra `export CASE=...` step. Site/profile paths needed by the campaign are part of the campaign configuration rather than hidden shell-session state.

`campaign run` performs the following sequence automatically:

1. reads the requested period and profile;
2. checks the first-cycle inputs, observation inputs for every required cycle and required commands;
3. refuses to start if the preflight fails;
4. creates a new clean campaign directory if it does not already exist;
5. generates the complete sequence of JEDI, MPAS and Obs2IODA steps with their dependencies;
6. starts `simpleWorkflow`;
7. on a later invocation, reuses the same campaign state and continues safely instead of rebuilding the campaign.

The example campaign requests 72 hours beginning at 2018-04-15 00Z. This gives 13 analyses and 12 six-hour MPAS forecast legs, ending at 2018-04-18 00Z.

## Campaign file

```yaml
campaign:
  name: m3-3days-20180415
  start: 2018-04-15T00:00:00Z
  duration: PT72H
  destination: cases/m3-3days-20180415

profile: profiles/jaci-mpas-3dfgat-x1.10242.yaml

execution:
  swf_command: swf
```

The profile contains the reusable paths and configuration sources for the validated JACI setup. The campaign file contains only information that normally changes between experiments.

## Profile root

A site profile can declare one explicit root for its scientific cases:

```yaml
profile:
  case_root: ../../../../../work/CASE
  initial_jedi_case: cases/jedi-2018041500-fgat-corrected
  cycling_jedi_case: cases/jedi-2018041500-fgat-corrected
  mpas_case: cases/mpas-2018041512-fgat-corrected
  obs2ioda_config: obs2ioda.yaml
```

`case_root` is resolved relative to the profile file. When it is present, relative JEDI, MPAS and Obs2IODA paths are resolved from that root. A relative `campaign.destination` is also resolved from the same root. This makes the campaign self-contained while retaining a reusable site profile.

Environment variables in campaign/profile paths remain supported for compatibility and for cases where they are genuinely useful. They are not required by the M3 JACI profile. If a referenced `$VAR` or `${VAR}` is not defined, the command stops with an explicit configuration error instead of treating the unresolved text as a filesystem path.

Paths inside `observation_acquisition.search_roots` retain their existing rule: relative entries are resolved from the profile file directory.

## Optional commands

These commands are useful for inspection or development but are not required before a normal `campaign run`:

```bash
monan-jedi-workflow campaign check  CAMPAIGN.yaml
monan-jedi-workflow campaign create CAMPAIGN.yaml
monan-jedi-workflow campaign status CAMPAIGN.yaml
monan-jedi-workflow campaign tui    CAMPAIGN.yaml
```

`campaign check` is read-only. `campaign create` prepares the campaign without submitting scientific jobs. `campaign status` shows the persisted execution state. `campaign tui` opens the interactive simpleWorkflow monitor.

## Restart

After correcting a problem, run the same command again:

```bash
monan-jedi-workflow campaign run CAMPAIGN.yaml
```

The existing campaign request is verified before reuse. A destination created for a different request is rejected instead of being silently overwritten.

## Lower-level commands

Commands such as `jedi-prepare`, `jedi-submit`, `mpas-validate` and `obs2ioda-doctor` remain available for development and diagnosis. They are implementation tools, not the normal procedure for running a campaign.
