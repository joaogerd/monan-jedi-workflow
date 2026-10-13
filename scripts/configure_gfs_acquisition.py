#!/usr/bin/env python3
"""Enable declared GFS acquisition in an existing tutorial and materialized case.

Preserves comments, scientific parameters and observation-provider choices.
Run with the same Python/environment used by monan-jedi-workflow.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

from monan_jedi_workflow.campaign import load_campaign_spec

BLOCK = '''  # Acquire only the GFS required by this initialization; reuse local data.
  acquisition:
    source: "{gfs_file}"
    url: "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{cycle_year}{cycle_month}{cycle_day}/{cycle_hour}/atmos/gfs.t{cycle_hour}z.pgrb2.0p25.f000"
    timeout_seconds: 300
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    args = parser.parse_args()
    spec = load_campaign_spec(args.campaign)
    paths = [spec.initial_mpas_case / 'wps.yaml']
    if spec.destination.exists():
        paths.append(spec.destination / 'initialization' / 'wps.yaml')
    changes = []
    for path in dict.fromkeys(paths):
        original = path.read_text()
        document = yaml.safe_load(original)
        wps = document.get('wps', {})
        if 'acquisition' in wps:
            print(f'[LOCAL] acquisition already configured: {path}')
            continue
        if not wps.get('variables', {}).get('gfs_file'):
            raise SystemExit(f'Cannot configure acquisition: wps.variables.gfs_file missing in {path}')
        updated, count = re.subn(r'^wps:[ \t]*\n', lambda _: 'wps:\n' + BLOCK, original, count=1, flags=re.MULTILINE)
        if count != 1:
            raise SystemExit(f'Expected a top-level wps mapping: {path}')
        expected = dict(document)
        expected['wps'] = {**wps, 'acquisition': yaml.safe_load('wps:\n' + BLOCK)['wps']['acquisition']}
        if yaml.safe_load(updated) != expected:
            raise SystemExit(f'Refusing unexpected configuration change: {path}')
        changes.append((path, original, updated))
    for path, original, updated in changes:
        backup = path.with_name(path.name + '.before-acquisition')
        with backup.open('x') as stream:
            stream.write(original)
        path.write_text(updated)
        print(f'[OK] GFS acquisition configured: {path}; backup: {backup}')


if __name__ == '__main__':
    main()
