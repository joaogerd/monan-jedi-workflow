#!/usr/bin/env python3
"""Read-only audit of the captured September 2025 reference (no model execution).

Run from an installed checkout. Inputs are the extracted campaign-configs archive
and its external config-sha256.txt; neither is modified. A successful audit only
establishes capture integrity and template reproducibility, not numerical skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from monan_jedi_workflow.analysis_cycle import analysis_cycle_context
from monan_jedi_workflow.cycle_context import parse_cycle_time
from monan_jedi_workflow.stage_config import render_text


def audit(root: Path, checksums: Path) -> dict:
    root = root.resolve()
    failures = []
    hashed = rendered = 0
    seen = set()
    for line in checksums.read_text().splitlines():
        expected, relative = line.split(maxsplit=1)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path in seen:
            raise ValueError(f'Unsafe or duplicate checksum path: {relative}')
        seen.add(path)
        hashed += 1
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f'checksum: {relative}')
    captured = {p.resolve() for p in root.rglob('*') if p.is_file()}
    for path in sorted(captured - seen):
        failures.append(f'unlisted file: {path.relative_to(root)}')
    if hashed != 2419:
        failures.append(f'expected 2419 captured files, found {hashed}')
    start = datetime(2025, 9, 1, tzinfo=timezone.utc)
    for index in range(29):
        timestamp = start + timedelta(hours=6 * index)
        cycle = parse_cycle_time(timestamp.isoformat())
        context = analysis_cycle_context(cycle, step_hours=6,
                                         background_offset_hours=-3, window_hours=6)
        context['model_tstep'] = 'PT20M'
        geometry = f'geometry/{timestamp:%Y%m%d%H}'
        pairs = [('variational.yaml', 'variational.yaml'),
                 ('namelist.atmosphere.outer.in', f'{geometry}/namelist.atmosphere.outer'),
                 ('namelist.atmosphere.inner.in', f'{geometry}/namelist.atmosphere.inner'),
                 ('streams.atmosphere.jedi.outer.in', f'{geometry}/streams.atmosphere.outer'),
                 ('streams.atmosphere.jedi.inner.in', f'{geometry}/streams.atmosphere.inner')]
        for source, target in pairs:
            generated = render_text((root / 'templates' / source).read_text(), context, label=source)
            actual = root / 'work/jedi' / cycle.cycle_id / target
            rendered += 1
            if generated.encode() != actual.read_bytes():
                failures.append(f'render: {actual.relative_to(root)}')
        if index < 28:
            model_context = cycle.render_context(lead_hours=6)
            for source, target in [('namelist.atmosphere.cycling.in', 'namelist.atmosphere'),
                                   ('streams.atmosphere.cycling.in', 'streams.atmosphere')]:
                generated = render_text((root / 'templates' / source).read_text(),
                                        model_context, label=source)
                actual = root / 'work/mpas' / cycle.cycle_id / target
                rendered += 1
                if generated.encode() != actual.read_bytes():
                    failures.append(f'render: {actual.relative_to(root)}')
    return {'scope': 'static reference integrity and beta temporal/template rendering',
            'numerically_validated': False, 'reference_cycles': 29,
            'reference_forecast_legs': 28, 'files_hashed': hashed,
            'rendered_files_compared': rendered,
            'checksum_manifest_sha256': hashlib.sha256(checksums.read_bytes()).hexdigest(),
            'failures': failures, 'passed': not failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('checksums', type=Path)
    args = parser.parse_args()
    result = audit(args.capture, args.checksums)
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
