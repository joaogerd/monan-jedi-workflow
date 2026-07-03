# Foreground Job Progress Reporting

## Purpose

`monan_jedi_workflow.core.progress` provides scheduler-neutral foreground status reporting for long-running backend work.

## Contract

Backends emit four generic events:

1. `submitted(backend, identifier, label)`;
2. `state(backend, identifier, state)`;
3. `heartbeat(backend, identifier, state, elapsed_seconds)`;
4. `completed(backend, identifier, terminal_state, elapsed_seconds)`.

The contract reports backend visibility only. It never declares a scientific stage successful; stage output validation remains responsible for that decision.

## Terminal behavior

`TerminalJobProgressReporter` always writes stable text status lines. When stdout is an interactive TTY, it also displays a minimal braille spinner between status lines. Redirected output and CI logs remain text-only.

Example:

```text
[JACI PBS] submitted 287527.pbs-ha (mpas_init_2026062000); waiting for scheduler completion.
[JACI PBS] 287527.pbs-ha state=Q; still waiting.
[JACI PBS] 287527.pbs-ha state=R; still waiting.
[JACI PBS] 287527.pbs-ha still state=R after 60s.
[JACI PBS] 287527.pbs-ha left qstat after 94s; scheduler wait completed.
```

## Extensibility

A Slurm, local-process, cloud, or future workflow backend can use the same `JobProgressReporter` contract without importing JACI or PBS code. Applications that own their own UI can inject `NullJobProgressReporter` or another implementation.
