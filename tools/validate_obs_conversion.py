#!/usr/bin/env python3
"""Validate observation conversion manifests and outputs.

This validator intentionally does not assume a particular converter or raw
observation format. It verifies:

- manifest consistency
- raw observation existence
- output existence
- output size > 0
- optional HDF5 readability for IODA outputs
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml

STATUS_OK=0
STATUS_WARN=1
STATUS_ERROR=2

try:
    import h5py
except Exception:
    h5py=None


def expand(path:str)->Path:
    return Path(os.path.expandvars(path)).expanduser()


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--strict',action='store_true')
    args=parser.parse_args()

    with open(args.manifest,'r',encoding='utf-8') as f:
        data=yaml.safe_load(f) or {}

    observations=data.get('observations',[])
    status=STATUS_OK

    for obs in observations:
        if not obs.get('enabled',True):
            continue

        name=obs.get('name','unnamed')
        source=expand(obs.get('source_file') or obs.get('prepbufr_file'))
        target=expand(obs.get('target_file') or obs.get('output_file'))

        if source.exists():
            print(f'[INFO] source exists for {name}: {source}')
        else:
            lvl='ERROR' if args.strict else 'WARN'
            print(f'[{lvl}] source missing for {name}: {source}')
            status=max(status, STATUS_ERROR if args.strict else STATUS_WARN)

        if target.exists():
            print(f'[INFO] target exists for {name}: {target}')
            if target.stat().st_size == 0:
                print(f'[ERROR] empty output for {name}: {target}')
                status=STATUS_ERROR

            if h5py and target.suffix in ['.h5','.hdf5','.nc4']:
                try:
                    with h5py.File(target,'r') as h:
                        roots=list(h.keys())
                    print(f'[INFO] {name}: HDF5 groups={roots}')
                except Exception as exc:
                    print(f'[ERROR] failed to open {target}: {exc}')
                    status=STATUS_ERROR
        else:
            lvl='ERROR' if args.strict else 'WARN'
            print(f'[{lvl}] output missing for {name}: {target}')
            status=max(status, STATUS_ERROR if args.strict else STATUS_WARN)

    if status==STATUS_OK:
        print('[INFO] Observation conversion validation completed')
        return 0

    if status==STATUS_WARN and not args.strict:
        return 0

    return 2

if __name__=='__main__':
    raise SystemExit(main())