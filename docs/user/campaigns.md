# Running a campaign

The normal user interface is one campaign YAML plus one command. Researchers do not need to remember the individual JEDI, MPAS and Obs2IODA stage commands.

After entering the standard MONAN-JEDI environment on JACI, where `CASE` is defined, the validated three-day M3 experiment is started with:

```bash
monan-jedi-workflow campaign run \
  examples/campaigns/m3-3days-20180415.yaml
```

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
  destination: $CASE/cases/m3-3days-20180415

profile: profiles/jaci-mpas-3dfgat-x1.10242.yaml

execution:
  swf_command: swf
```

The profile contains the reusable paths and configuration sources for the validated JACI setup. The campaign file contains only information that normally changes between experiments.

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
