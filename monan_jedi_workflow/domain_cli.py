"""Side-effect-free argument contract for the independent domain apps.

This module parses requests only. It does not prepare or execute operations.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import re

VERBS = ('inspect', 'check', 'prepare', 'run', 'validate', 'status')

@dataclass(frozen=True)
class DomainRequest:
    app: str
    operation: str
    action: str
    config: Path
    cycle: str | None
    json_output: bool
    source: str | None
    engine: str | None


def _utc_cycle(value: str) -> str:
    """Require an explicit ISO timestamp in UTC, preserving its spelling."""
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)', value):
        raise argparse.ArgumentTypeError('cycle must be an explicit UTC timestamp, e.g. 2025-09-01T00:00:00Z')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise argparse.ArgumentTypeError(f'invalid cycle: {value}') from error
    if parsed.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError('cycle must use UTC')
    return value


def _actions(parser: argparse.ArgumentParser, app: str, operation: str) -> argparse._SubParsersAction:
    actions = parser.add_subparsers(dest='action', required=True)
    verbs = ('inspect', 'check', 'export') if app == 'campaign' else VERBS
    for verb in verbs:
        action = actions.add_parser(verb, allow_abbrev=False)
        action.set_defaults(operation=operation, source=None, engine=None, cycle=None)
        action.add_argument('config', type=Path)
        action.add_argument('--json', dest='json_output', action='store_true')
        if app != 'campaign':
            action.add_argument('--cycle', required=True, type=_utc_cycle)
        if app == 'obs':
            action.add_argument('--source')
        if app == 'campaign' and verb == 'export':
            action.add_argument('--engine', default='simpleworkflow')
    return actions


def parse_request(app: str, argv: list[str]) -> DomainRequest:
    """Parse a domain request without inspecting files or importing backends."""
    if app not in {'obs', 'jedi', 'mpas', 'diagnostics', 'campaign'}:
        raise ValueError(f'unknown domain app: {app}')
    parser = argparse.ArgumentParser(prog=app, allow_abbrev=False)
    if app == 'obs':
        operations = parser.add_subparsers(dest='operation', required=True)
        for operation in ('acquire', 'convert'):
            _actions(operations.add_parser(operation, allow_abbrev=False), app, operation)
    elif app == 'mpas':
        actions = _actions(parser, app, 'forecast')
        _actions(actions.add_parser('init', allow_abbrev=False), app, 'init')
    else:
        _actions(parser, app, 'assimilation' if app == 'jedi' else app)
    return DomainRequest(app=app, **vars(parser.parse_args(argv)))
