# First platform beta — execution record

User authorized complete first test beta after approving domain separation and
shared verbs. Execution extends the parser slice without another design gate.

- [x] Domain configuration references, declared-file paths, installed catalog and provenance.
- [x] Native JEDI/MPAS/init/Obs2IODA preparation and validation adapters.
- [x] Worker execution inside existing allocation; explicit sequential local mode.
- [x] Per-cycle acquisition, conversion selection, diagnostics and workflow export.
- [x] Actual-runtime ownership, atomic records, input/product hashes and failure evidence.
- [x] Short executable apps, wheel package data, artificial installation fixture.
- [x] Regression tests for reviewer findings and whole-suite verification.
- [ ] Scientific acceptance on JACI using an isolated reference experiment.

Rulings: keep native scientific stage schemas for compatibility; expose native
application overrides rather than silently translating minimizer options. First
exporter expands timestamps into a static task graph; only simpleWorkflow
executes it. Acquisition in this beta handles direct local/HTTP(S) files, not
new archive providers. Diagnostics report configured departures rather than
inventing a mapping from every JEDI build's HofX output.

Independent review found failed-converter partial-output reuse, foreign
runtime overwrite, shared-runtime lock scope, omitted dependency hashes,
init output path inconsistency and exclusive-calendar handling. Each finding
received a failing regression test before correction. Numerical equivalence and
HPC execution remain explicit acceptance work, not claimed results.

Verification: 222 tests passed, 7 pre-existing warnings; lint and diff checks clean.
Installed wheel exercised all five apps outside the checkout. simpleWorkflow 0.6.2
completed 30 artificial tasks (3 initialization + 27 cycling). No real HPC execution.
