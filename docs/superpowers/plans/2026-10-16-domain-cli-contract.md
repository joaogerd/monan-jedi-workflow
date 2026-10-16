# Domain CLI contract — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Establish the shared CLI contract without changing scientific recipes or adding campaign execution.
**Architecture:** Add an independent parser and request model for the five domain apps. Keep legacy entry points intact. Connect scientific backends in subsequent reviewed slices, rather than disguising scheduler submission as run.
**Tech Stack:** Python >=3.10, argparse, pytest >=8.
**Spec:** ../specs/2026-10-16-platform-domain-apps-design.md

## Global Constraints
- Apps: obs, jedi, mpas, diagnostics, campaign.
- Common verbs: inspect, check, prepare, run, validate, status where applicable.
- Specialized operation precedes verb; obs requires acquire or convert.
- campaign supports inspect/check/export, never run.
- No cycle executor, implicit prepare, cross-domain dispatch, calendar loop or scientific changes.
- Existing entry points remain compatible.
- First slice provides a tested interface contract; it does not advertise executable backends.

## Baseline findings
The remote branch was created from current main. The user's local checkout is older: local pyproject points at cli_extended; remote points at cli_frontend and includes numpy/netCDF4. Never implement against that stale checkout. Obtain a snapshot of the remote branch before running baseline tests or editing product code. Shell DNS is unavailable; GitHub connector reads/writes work. System Python lacks pytest; no passing baseline has been established.

Remote cli_frontend currently acquires campaign observations for campaign create/run. That behavior must not be inherited by the new campaign app. pyproject excludes configs from package discovery. These require later integration slices.

## Review Focus
- Missing cycle rejected for scientific operations.
- start/end flags rejected by scientific parsers.
- OBS root run rejected to avoid implicit acquisition+conversion.
- campaign run rejected without invoking legacy campaign behavior.
- Parsing never downloads, submits jobs or imports scientific backend modules.

## File Structure
- Create monan_jedi_workflow/domain_cli.py: shared argument grammar and immutable request model.
- Create tests/test_domain_cli.py: grammar, invalid inputs and side-effect boundaries.
- Create docs/developer/domain-cli-contract.md: public grammar and mapping to the approved spec.
- No pyproject entry-point changes in this first slice; install apps only when handlers exist.

### Task 1: Shared domain request grammar
**Interfaces:** DomainRequest(app: str, operation: str, action: str, config: Path, cycle: str | None, json_output: bool, source: str | None, engine: str | None). parse_request(app: str, argv: list[str]) -> DomainRequest.

- [x] Write parameterized tests for jedi/mpas/diagnostics common verbs, obs acquire/convert common verbs, mpas init common verbs and campaign inspect/check/export.
- [x] Assert invalid combinations exit with parser code 2: missing cycle, obs run, campaign run, scientific --start/--end.
- [x] Run python -m pytest tests/test_domain_cli.py -q and confirm failure from missing module.
- [x] Implement immutable DomainRequest and parse_request in domain_cli.py using argparse; map root MPAS to forecast and root JEDI to assimilation. Accept --json for all requests, --source only OBS and --engine only campaign export; default export engine simpleworkflow.
- [x] Test --source and --engine misuse and explicit UTC timestamp validation; keep date parsing independent of backend modules.
- [x] Run focused tests and verify all cases pass.
- [x] Commit this independently testable parser contract.

### Task 2: Side-effect boundary and documentation
**Consumes:** parse_request and DomainRequest from Task 1.
**Produces:** a documented, tested interface suitable for backend binding in the next plan.

- [x] Add tests that parse all allowed verbs with nonexistent config paths without reading files or loading backend modules. Existence and dependencies are the handler's responsibility, not the parser's.
- [x] Run focused tests and confirm behavior.
- [x] Document shared meanings and distinctions: check inputs, prepare runtime, run prepared operation, validate products, inspect/status read only.
- [x] Document that entry points remain legacy and the new app handlers are not delivered by this slice.
- [x] Run python -m pytest -q on the current remote snapshot after dependencies are available; report missing dependencies separately from test failures.
- [x] Commit documentation and tests.

## Follow-on slices
1. Resolve principal plus domain YAMLs without unrelated dependencies; distribute catalog and prove installed-wheel access.
2. Bind inspect/check/prepare/validate/status to per-domain APIs.
3. Extract worker execution inside allocation; keep a single PBS owner and no implicit submit.
4. Bind OBS acquisition/conversion and standalone MPAS initialization.
5. Add diagnostics app and campaign export with no acquisition/execution side effects.
6. Exercise reference configuration equivalence, recovery and a real isolated JACI cycle through the orchestrator.

Each follow-on slice needs exact signatures grounded in the current backend source before implementation. This plan deliberately does not promise the whole beta in its first parser task.

## Execution result — 2026-10-16

Completed parser slice: 58 focused tests passed; full suite 191 passed with 7 pre-existing warnings (baseline 133 passed). Independent reviewer found no important bugs; manual grammar matrix passed.

Rulings: remote snapshot reconstructed through connector because shell DNS unavailable, preserving user checkout. Corrected selector test to include required run verb. Included MPAS init in root help after failing regression test.

Deferred minor test improvements: parameterize missing-cycle/start/end rejection across every operation; extend side-effect testing to import-time reads and every backend import. Reviewer manually checked operation paths.

New entry points and scientific backend bindings remain follow-on work.
