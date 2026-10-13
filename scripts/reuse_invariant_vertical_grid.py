#!/usr/bin/env python3
"""Reuse invariant geometry for GFS initialization; preserve failed state and configs."""
import argparse
import json
import re
import shutil
from datetime import timedelta
from pathlib import Path

from monan_jedi_workflow.campaign import load_campaign_spec
from monan_jedi_workflow.corrected_campaign import _iso, _parse_cycle
from monan_jedi_workflow.init_stage import _load
from monan_jedi_workflow.stage_config import resolve_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign',type=Path)
    args = parser.parse_args()
    spec = load_campaign_spec(args.campaign)
    cycle = _iso(_parse_cycle(spec.start_cycle)-timedelta(hours=spec.cycle_interval_hours))
    configs = [spec.initial_mpas_case]
    if spec.destination.exists():
        configs.append(spec.destination/'initialization')
    changes = {}
    states = []
    for root in dict.fromkeys(configs):
        run = _load(root,cycle)
        reference = next(entry['source'] for entry in run.config['links'] if entry['target']=='x1.10242.static.nc')
        reference = resolve_path(reference,config_dir=run.config_dir,context=run.context,label='invariant reference')
        if not reference.is_file():
            raise SystemExit(f'Invariant does not exist: {reference}')
        for entry in run.config['templates']:
            if entry['target']=='namelist.init_atmosphere':
                path=resolve_path(entry['source'],config_dir=run.config_dir,context=run.context,label='init namelist')
                text=path.read_text()
                updated,count=re.subn(r'(config_vertical_grid[ \t]*=[ \t]*)\.true\.',r'\1.false.',text,flags=re.IGNORECASE)
                if not count and not re.search(r'config_vertical_grid\s*=\s*\.false\.',text,re.IGNORECASE):
                    raise SystemExit(f'Cannot find vertical-grid setting in {path}')
                changes[path]=updated
        path=root/'mpas_init.yaml'
        text=path.read_text()
        current=run.config['validation'].get('geometry_reference')
        if current is None:
            text,count=re.subn(r'^([ \t]*)validation:[ \t]*$',lambda m:m[0]+'\n'+m[1]+'  geometry_reference: '+json.dumps(str(reference)),text,count=1,flags=re.MULTILINE)
            if count!=1:
                raise SystemExit(f'Cannot locate validation in {path}')
        else:
            existing=resolve_path(current,config_dir=run.config_dir,context=run.context,label='geometry reference')
            if existing!=reference:
                raise SystemExit(f'Refusing to replace different geometry reference in {path}')
        text=re.sub(r'required_log_markers:[ \t]*\[\]', 'required_log_markers: ["Finished running the init_atmosphere core"]',text)
        changes[path]=text
        for value in run.config['validation']['required_outputs']:
            state=resolve_path(value,config_dir=run.config_dir,context=run.context,label='initial state')
            if state.is_file():
                states.append(state)
    for state in dict.fromkeys(states):
        backup=state.parent/'before-invariant-grid'/state.name
        if not backup.exists():
            backup.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(state,backup)
            print(f'[OK] preserved previous state: {backup}')
    for path,updated in changes.items():
        text=path.read_text()
        if text==updated:
            print(f'[LOCAL] already configured: {path}')
            continue
        backup=path.with_name(path.name+'.before-invariant-grid')
        with backup.open('x') as stream:
            stream.write(text)
        path.write_text(updated)
        print(f'[OK] invariant geometry configured: {path}; backup: {backup}')


if __name__=='__main__':
    main()
