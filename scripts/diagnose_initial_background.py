#!/usr/bin/env python3
"""Read-only diagnosis of cold-start fields, invariant geometry and MPAS failure.

This does not edit configuration, reset state, submit jobs or change products.
It compares actual declared inputs, not inferred files from a naming convention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import timedelta
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

from monan_jedi_workflow.campaign import load_campaign_spec
from monan_jedi_workflow.corrected_campaign import _iso, _parse_cycle
from monan_jedi_workflow.mpas_stage import load_mpas_run
from monan_jedi_workflow.stage_config import resolve_path

GEOMETRY = ('latCell','lonCell','indexToCellID','zgrid','dzu','rdzu','rdzw','zz',
            'zxu','zb','zb3','fzm','fzp','cf1','cf2','cf3')
FIELDS = ('u','w','theta','rho','theta_base','rho_base','pressure_base','pressure_p',
          'surface_pressure','qv','qv_init','u_init','v_init','t_init','smois','tslb')


def values(variable):
    selection = tuple(0 if dim == 'Time' else slice(None) for dim in variable.dimensions)
    return np.ma.asarray(variable[selection], dtype=np.float64)


def stats(variable):
    array = values(variable)
    data = array.compressed()
    finite = np.isfinite(data)
    valid = data[finite]
    return {'shape': list(array.shape), 'masked': int(np.ma.count_masked(array)),
            'nonfinite': int((~finite).sum()), 'min': float(valid.min()) if valid.size else None,
            'max': float(valid.max()) if valid.size else None}


def compare_geometry(initial, invariant):
    report = {}
    for name in GEOMETRY:
        if name not in initial.variables or name not in invariant.variables:
            report[name] = {'in_initial': name in initial.variables, 'in_invariant': name in invariant.variables}
            continue
        left, right = values(initial.variables[name]), values(invariant.variables[name])
        if left.shape != right.shape:
            report[name] = {'shape_initial': list(left.shape), 'shape_invariant': list(right.shape), 'compatible': False}
            continue
        finite = np.isfinite(left.filled(np.nan)) & np.isfinite(right.filled(np.nan))
        diff = np.abs(left.filled(np.nan)-right.filled(np.nan))
        report[name] = {'max_abs_difference': float(diff[finite].max()) if finite.any() else None,
                        'close': bool(finite.all() and np.allclose(left, right, rtol=1e-7, atol=1e-8))}
    return report


def fingerprint(path):
    result = {'path': str(path), 'resolved': str(path.resolve()), 'exists': path.is_file()}
    if path.is_file():
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                digest.update(chunk)
        result['sha256'] = digest.hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    args = parser.parse_args()
    spec = load_campaign_spec(args.campaign)
    cycle = _iso(_parse_cycle(spec.start_cycle)-timedelta(hours=spec.cycle_interval_hours))
    config = spec.destination/'initialization' if spec.destination.exists() else spec.initial_mpas_case
    run = load_mpas_run(config, cycle)
    inputs = {}
    for entry in run.config['links']:
        target = entry['target']
        if target.startswith('mpas.init.') or target == 'x1.10242.invariant.nc' or target == 'mpas_atmosphere':
            key = 'initial' if target.startswith('mpas.init.') else ('invariant' if target.endswith('.nc') else 'executable')
            inputs[key] = resolve_path(entry['source'], config_dir=run.config_dir, context=run.context, label='diagnostic input')
    for key in ('initial','invariant','executable'):
        if key not in inputs:
            raise SystemExit(f'Cannot identify declared {key} input in {config}/mpas.yaml')
    result = {'cycle':cycle, 'run_dir':str(run.run_dir),
              'inputs':{key: {'path':str(path), 'resolved':str(path.resolve())} for key,path in inputs.items()}}
    with Dataset(inputs['initial']) as initial, Dataset(inputs['invariant']) as invariant:
        result['dimensions_initial'] = {name:len(dim) for name,dim in initial.dimensions.items()}
        result['dimensions_invariant'] = {name:len(dim) for name,dim in invariant.dimensions.items()}
        result['initial_fields'] = {name:stats(initial.variables[name]) if name in initial.variables else 'MISSING' for name in FIELDS}
        result['geometry_comparison'] = compare_geometry(initial,invariant)
        if 'zgrid' in initial.variables:
            var = initial.variables['zgrid']
            heights = values(var)
            dims = [dim for dim in var.dimensions if dim != 'Time']
            axis = dims.index('nVertLevelsP1')
            thickness = np.ma.asarray(np.diff(heights,axis=axis)).compressed()
            good = thickness[np.isfinite(thickness)]
            result['initial_layer_thickness'] = {'min':float(good.min()) if good.size else None,
                                                 'max':float(good.max()) if good.size else None,
                                                 'nonfinite':int((~np.isfinite(thickness)).sum())}
    result['current_binary'] = fingerprint(inputs['executable'])
    old = Path('/p/projetos/monan_das') / inputs['executable'].parts[4] / 'work/CASE/cases/m3-3days-20180415/work/mpas/20180415T000000Z/mpas_atmosphere'
    # This optional historical path is provenance only; absence is not an error.
    result['m3_binary_optional'] = fingerprint(old)
    stderr = run.run_dir/'stderr.log'
    if stderr.is_file():
        matches = re.findall(r'^#\d+\s+.*?\bin\s+([^\n]+)\n\s*at\s+([^\n]+)', stderr.read_text(errors='replace'), re.MULTILINE)
        result['backtrace_functions'] = list(dict.fromkeys(f'{func.strip()} at {source.strip()}' for func,source in matches))[:20]
    init_log = config/'work/mpas-init'/run.cycle.cycle_id/'log.init_atmosphere.0000.out'
    if init_log.is_file():
        result['init_log_tail'] = init_log.read_text(errors='replace').splitlines()[-45:]
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__ == '__main__':
    main()
