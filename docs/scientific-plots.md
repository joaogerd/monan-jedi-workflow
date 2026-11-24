# Scientific figures from MPAS-JEDI feedback

The `experiment status` command verifies orchestration, and `diagnose`
investigates failures. **Neither demonstrates scientific quality.**
The optional `experiment plots` command reads the **actual JEDI observation
feedback** saved in the experiment and produces paired O–B/O–A figures, plus campaign continuity and variational
cost convergence when the required manifests, logs and workflow state exist.

## Usage (no jobs, read-only scientific products)

```bash
cd /p/projetos/monan_das/joao.gerd/work/teste-7dias
python -m pip install -e '/p/projetos/monan_das/joao.gerd/projects/monan-jedi-workflow[plots]'
experiment plots .
```

The plotting dependency is optional. It is installed into the **login-node**
Python environment; no Conda/Python installation is needed on PBS compute
nodes, and no scientific job is resubmitted.

To limit variables or choose an output directory:

```bash
experiment plots . --variables airTemperature,stationPressure,atmosphericRefractivity
experiment plots . --output diagnostics/figures
```

Output directory (default: `diagnostics/figures/`):

- `<observer>_<variable>.png`: a three-panel diagnostic (RMSE, bias, and
  number of paired accepted observations per cycle)
- `paired_feedback.csv`: tabular values for all available combinations
- `campaign_completion.png`: timeline, only if **every** expected cycle has
  valid JEDI/MPAS stage manifests and SQLite records all tasks successful
- `jedi_cost_convergence.png`: normalized quadratic cost J/J₀ from JEDI logs,
  one line per cycle with usable data (partial coverage is explicitly reported)
- `campaign_completion.csv`, `jedi_convergence.csv`, `jedi_cost_iterations.csv`:
  traced operational and minimizer evidence, including JEDI log SHA-256
- `manifest.json`: expected campaign cycles, absent feedback files,
  skipped variables (with reasons), and generated figure names

## Scientific interpretation

Observations are paired at the *same locations* for O–B and O–A. Selection is
the intersection of available EffectiveQC groups equal to zero, finite and
unmasked values. Observations and both HofX fields must have matching shapes. The physical
unit is taken from `ObsValue`: `hofx0` and `hofx1` may omit their `units`
attribute (as in operational JEDI output), but an explicitly conflicting unit
is rejected. If `ObsValue` has no unit, the variable is skipped and explained
in the manifest. This is a metadata convention, not a numerical unit conversion.
The figures do **not** calculate forecast scores or establish independent
validation: they are fit-to-assimilated-observations diagnostics.

The command reads feedback files from

```text
work/jedi/<YYYYMMDDTHHMMSSZ>/Data/os/
  obsout_3dvar_sondes.nc4
  obsout_3dvar_sfc.nc4
  obsout_3dvar_gnssroref.nc4
```

If a file is missing or lacks `ObsValue`, `hofx0`, `hofx1` or compatible
`EffectiveQC`, no values are fabricated. The manifest records the gap and
the command exits nonzero if no figure can be generated.

A successful `experiment status` or PBS `Exit_status=0` does not imply
these diagnostics exist or that a model forecast is scientifically accurate.
For maps, vertical diagnostics, independent verification, and other
observation formats, new data readers/validation contracts must be added.

## Historical M3 methodology and compatibility

The convergence and continuity readers adapt the historical script
[`scripts/generate_campaign_figures.py`](https://github.com/joaogerd/monan-jedi-workflow/blob/feature/2025-reference-case/scripts/generate_campaign_figures.py)
to the **current** `campaign.yaml`, `.simpleworkflow/state.sqlite3`, JEDI
`jedi-validation.json`, MPAS `mpas-validation.json` and real `jedi.stdout.log`
contracts. No historical campaign results are copied or mixed into the new
experiment.

The total quadratic cost `Quadratic cost function: J (iter)` is extracted
without conflating it with `Jb` or `JoJc`. If iteration zero is missing, the
initial nonlinear `CostFunction: Nonlinear J` is used as in historical M3.
Repeated outer-loop sequences are explicitly rejected, not spliced together.
Only real cost curves contribute to the figure. For incomplete manifests,
missing logs or non-success SQLite states, the report retains the specific
failure rather than depicting all-green continuity.

The manifest's `operational_and_variational` section reports coverage,
monotonicity and the mean cost reduction. **Cost convergence does not imply
forecast quality.** Check all gaps before interpreting the campaign as
scientifically validated.
