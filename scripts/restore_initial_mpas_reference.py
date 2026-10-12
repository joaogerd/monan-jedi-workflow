#!/usr/bin/env python3
"""Restore the M3 initial-forecast templates and endian setting in an existing case.

Only the initial forecast is changed. Backups preserve all replaced files.
The initial condition and successful WPS/init_atmosphere products are retained.
"""
import argparse
import re
from datetime import timedelta
from pathlib import Path

from monan_jedi_workflow.campaign import load_campaign_spec
from monan_jedi_workflow.corrected_campaign import _iso, _parse_cycle
from monan_jedi_workflow.mpas_stage import load_mpas_run
from monan_jedi_workflow.stage_config import resolve_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    args = parser.parse_args()
    spec = load_campaign_spec(args.campaign)
    cycle = _iso(_parse_cycle(spec.start_cycle)-timedelta(hours=spec.cycle_interval_hours))
    configs = [spec.initial_mpas_case]
    if spec.destination.exists():
        configs.append(spec.destination/'initialization')
    reference = Path(__file__).resolve().parents[1]/'examples/case/templates'
    changes = {}
    for config_dir in dict.fromkeys(configs):
        run = load_mpas_run(config_dir, cycle)
        for entry in run.config['templates']:
            name = {'namelist.atmosphere': 'namelist.atmosphere.initial.in',
                    'streams.atmosphere': 'streams.atmosphere.initial.in'}.get(entry['target'])
            if name:
                target = resolve_path(entry['source'], config_dir=run.config_dir,
                                      context=run.context, label='initial forecast template')
                changes[target] = (reference/name).read_text()
        config_path = config_dir/'mpas.yaml'
        text = config_path.read_text()
        setting = run.config['pbs'].get('environment', {}).get('GFORTRAN_CONVERT_UNIT')
        if setting is None:
            text, count = re.subn(r'^([ \t]*)environment:[ \t]*$',
                                 lambda m: m[0]+'\n'+m[1]+'  GFORTRAN_CONVERT_UNIT: "big_endian:101-200"',
                                 text, count=1, flags=re.MULTILINE)
            if count != 1:
                raise SystemExit(f'Cannot locate pbs.environment in {config_path}')
            changes[config_path] = text
        elif setting != 'big_endian:101-200':
            raise SystemExit(f'Refusing to replace custom endian setting in {config_path}: {setting}')
    for path, content in changes.items():
        original = path.read_text()
        if original == content:
            print(f'[LOCAL] reference already present: {path}')
            continue
        backup = path.with_name(path.name+'.before-m3-initial')
        with backup.open('x') as stream:
            stream.write(original)
        path.write_text(content)
        print(f'[OK] restored initial M3 reference: {path}; backup: {backup}')


if __name__ == '__main__':
    main()
