#!/usr/bin/env python3
"""Restore the validated JACI PALS launcher in source and materialized cases.

Preserves comments and scientific settings. Refuses to replace a custom launcher.
"""
import argparse
import os
import re
from pathlib import Path

from monan_jedi_workflow.campaign import load_campaign_spec

LAUNCHER = '/opt/cray/pals/1.6/bin/mpiexec'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    args = parser.parse_args()
    if not os.access(LAUNCHER, os.X_OK):
        raise SystemExit(f'Validated JACI launcher is not executable: {LAUNCHER}')
    spec = load_campaign_spec(args.campaign)
    paths = [spec.mpas_case/'mpas.yaml', spec.cycling_jedi_case/'jedi.yaml',
             spec.initial_mpas_case/'mpas.yaml', spec.initial_mpas_case/'mpas_init.yaml']
    if spec.destination.exists():
        paths += [spec.destination/'mpas.yaml', spec.destination/'jedi.yaml',
                  spec.destination/'initialization/mpas.yaml', spec.destination/'initialization/mpas_init.yaml']
    changes = []
    for path in dict.fromkeys(paths):
        text = path.read_text()
        if re.search(r'^\s+launcher:\s*'+re.escape(LAUNCHER)+r'\s*$', text, re.MULTILINE):
            print(f'[LOCAL] PALS already configured: {path}')
            continue
        updated, count = re.subn(r'^([ \t]+launcher:)[ \t]*mpiexec[ \t]*$', lambda m: m[1]+' '+LAUNCHER,
                                text, flags=re.MULTILINE)
        if count != 1:
            raise SystemExit(f'Refusing to replace custom/missing launcher in {path}')
        changes.append((path, text, updated))
    for path, text, updated in changes:
        backup = path.with_name(path.name+'.before-pals')
        with backup.open('x') as stream:
            stream.write(text)
        path.write_text(updated)
        print(f'[OK] configured PALS: {path}; backup: {backup}')


if __name__ == '__main__':
    main()
