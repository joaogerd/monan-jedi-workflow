"""Prepare the fixed two-analysis September 2025 acceptance experiment.

A reference-specific validation utility, not a generic cycle runner. Execution
belongs to the exported orchestrator or the generated explicit user PBS shell.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import shutil

import yaml

CYCLES = ('20250901T000000Z', '20250901T060000Z')
TIMES = ('2025-09-01T00:00:00Z', '2025-09-01T06:00:00Z')


def _yaml(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _hash(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def generate_pilot(reference: Path, destination: Path) -> None:
    reference, destination = reference.resolve(), destination.resolve()
    if reference.is_relative_to(destination) or destination.is_relative_to(reference):
        raise ValueError('Reference and destination must not overlap')
    if destination.exists():
        raise FileExistsError(destination)
    documents = {name: yaml.safe_load((reference / f'{name}.yaml').read_text())
                 for name in ('jedi', 'mpas')}
    cycle = documents['jedi']['jedi']['cycle']
    if any(cycle.get(k) != v for k, v in {'step_hours': 6, 'background_offset_hours': -3,
                                         'window_hours': 6, 'first_cycle': TIMES[0]}.items()):
        raise ValueError('Reference does not match the September 2025 temporal contract')
    for name in ('jedi', 'mpas'):
        if documents[name][name]['pbs']['mpiprocs'] != 128:
            raise ValueError('Reference must use 128 MPI ranks')
    for directory in ('templates', 'runtime-skeleton'):
        if not (reference / directory).is_dir():
            raise ValueError(f'Missing reference {directory}')
    destination.mkdir(parents=True)
    science = destination / 'science'
    science.mkdir()
    for directory in ('templates', 'runtime-skeleton'):
        shutil.copytree(reference / directory, science / directory, symlinks=True)
    jedi = documents['jedi']['jedi']
    jedi['run_dir'] = str(destination / 'work/jedi/{cycle_id}')
    for field in ('source', 'initial_source'):
        jedi['background'][field] = str(destination / 'work/background/{cycle_id}/trajectory.nc')
    jedi['analysis_base_state']['source'] = str(destination / 'work/background/{cycle_id}/state.nc')
    jedi['runtime']['skeleton'] = str(science / 'runtime-skeleton')
    for link in jedi.get('links', []):
        if link['source'].startswith('work/obs/'):
            link['source'] = str(reference / link['source'])
    for template in jedi['templates']:
        template['source'] = str(science / 'templates' / Path(template['source']).name)
    model = documents['mpas']['mpas']
    model['variables']['campaign_root'] = str(destination)
    model['run_dir'] = str(destination / 'work/mpas/{cycle_id}')
    for template in model['templates']:
        template['source'] = str(science / 'templates' / Path(template['source']).name)
    for name, document in documents.items():
        _yaml(science / f'{name}.yaml', document)
    for index, cycle_id in enumerate(CYCLES):
        background = destination / 'work/background' / cycle_id
        background.mkdir(parents=True)
        for name, hour in [('trajectory.nc', '03'), ('state.nc', '06')]:
            source = (reference / 'work/background' / cycle_id / name if index == 0 else
                      destination / 'work/mpas' / CYCLES[0] / f'mpasout.2025-09-01_{hour}.00.00.nc')
            (background / name).symlink_to(source)
    _yaml(destination / 'experiment.yaml', {
        'schema_version': 1, 'experiment': {'name': 'reference-20250901-two-analyses',
        'destination': str(destination)}, 'site': {'execution': {'mode': 'pbs'}},
        'jedi': './science/jedi.yaml', 'mpas': './science/mpas.yaml', 'cycle': {'interval': 'PT6H'}})
    _yaml(destination / 'campaign.yaml', {
        'schema_version': 1, 'experiment': './experiment.yaml',
        'calendar': {'start': TIMES[0], 'end': TIMES[1], 'interval': 'PT6H'},
        'operations': ['jedi', 'mpas'], 'last_cycle': {'forecast': False},
        'output': './workflow.yaml'})
    metadata = {'reference': str(reference), 'candidate': str(destination),
                'scope': 'two analyses with candidate forecast handoff; historical IODA reused',
                'reference_configs_sha256': {n: _hash(reference / f'{n}.yaml') for n in documents}}
    (destination / 'pilot.json').write_text(json.dumps(metadata, indent=2) + '\n')
    # The shell is deliberately explicit and user-owned; no period/cycle runner is added.
    root = shlex.quote(str(destination))
    lines = ['#!/bin/bash', '#PBS -N monan-beta-pilot', '#PBS -q pesqmidi',
             '#PBS -l select=1:ncpus=128:mpiprocs=128', '#PBS -l walltime=03:00:00',
             '#PBS -V', 'set -euo pipefail', ': "${PBS_JOBID:?Submit this shell with qsub}"',
             f'cd {root}', 'exec >pilot.stdout.log 2>pilot.stderr.log',
             'python -m monan_jedi_workflow.scientific_pilot preflight .']
    for app, time in [('jedi', TIMES[0]), ('mpas', TIMES[0]), ('jedi', TIMES[1])]:
        for verb in ('check', 'prepare', 'run', 'validate'):
            lines.append(f'{app} {verb} experiment.yaml --cycle {time}')
    lines.append('python -m monan_jedi_workflow.scientific_pilot compare .')
    (destination / 'run-pilot.pbs').write_text('\n'.join(lines) + '\n')


def preflight(root: Path) -> dict:
    import os
    from .site import runtime_contract_context
    root = root.resolve()
    meta = json.loads((root / 'pilot.json').read_text())
    reference = Path(meta['reference'])
    install = Path(os.environ['MONAN_JEDI_INSTALL_ROOT'])
    stack = Path(os.environ['STACK_ROOT'])
    contract = runtime_contract_context(install, stack)
    inputs = [install / 'share/monan-jedi/install-manifest.json',
              install / 'bin/mpasjedi_variational.x', install / 'bin/mpas_atmosphere']
    # Comparison inputs must exist before spending a PBS allocation.
    for cycle_id, hour in zip(CYCLES, ('00', '06')):
        base = reference / 'work/jedi' / cycle_id
        inputs.append(base / f'Data/states/mpas.3dfgat.2025-09-01_{hour}.00.00.nc')
        inputs.extend(base / f'Data/os/obsout_3dvar_{kind}.nc4' for kind in ('sondes', 'sfc', 'gnssroref'))
        inputs.append(base / 'jedi.stdout.log')
    inputs.extend(reference / 'work/mpas' / CYCLES[0] / f'mpasout.2025-09-01_{hour}.00.00.nc' for hour in ('03', '06'))
    inputs += [root / 'work/background' / CYCLES[0] / name for name in ('trajectory.nc', 'state.nc')]
    for cycle in ('2025090100', '2025090106'):
        inputs += [reference / 'work/obs' / cycle / f'{name}_obs_{cycle}.h5'
                   for name in ('sondes', 'sfc', 'gnssro')]
    missing = [str(p) for p in inputs if not p.is_file()]
    if missing:
        raise ValueError('Missing real reference/runtime inputs: ' + ', '.join(missing))
    for cycle_id in CYCLES:
        _costs(reference / 'work/jedi' / cycle_id / 'jedi.stdout.log')
    # Verify the candidate owns the two future inputs; never substitute historical forecasts.
    for name, hour in [('trajectory.nc', '03'), ('state.nc', '06')]:
        link = root / 'work/background' / CYCLES[1] / name
        expected = root / 'work/mpas' / CYCLES[0] / f'mpasout.2025-09-01_{hour}.00.00.nc'
        if not link.is_symlink() or link.readlink() != expected:
            raise ValueError(f'Invalid candidate handoff: {link}')
    for name, expected in meta['reference_configs_sha256'].items():
        if _hash(reference / f'{name}.yaml') != expected:
            raise ValueError(f'Reference configuration changed: {name}')
    result = {'runtime_contract': contract, 'inputs_sha256': {str(p): _hash(p) for p in inputs},
              'environment': {k: os.environ.get(k) for k in
                              ('MONAN_JEDI_INSTALL_ROOT', 'STACK_ROOT', 'PBS_JOBID', 'PBS_O_HOST')},
              'scientifically_validated': False}
    (root / 'preflight.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


_NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][-+]?\d+)?'


def _costs(path: Path):
    text = path.read_text()
    initial = re.findall(r'CostFunction:\s*Nonlinear J\s*=\s*(' + _NUMBER + ')', text)
    quadratic = re.findall(r'Quadratic cost function:\s*J\s*\(\s*(\d+)\s*\)\s*=\s*(' + _NUMBER + ')', text)
    # Fixed reference: one outer loop, ten inner iterations. Reject incomplete/combined attempts.
    if not initial or [int(i) for i, _ in quadratic] not in (list(range(1, 11)), list(range(11))):
        raise ValueError(f'Missing or ambiguous reference cost sequence: {path}')
    number = lambda x: float(x.replace('D', 'E').replace('d', 'e'))
    if any(not math.isfinite(number(x)) or number(x) < 0 for x in initial + [v for _, v in quadratic]):
        raise ValueError(f'Invalid cost values: {path}')
    return {'nonlinear': [number(x) for x in initial],
            'quadratic': [[int(i), number(v)] for i, v in quadratic]}


def compare_pilot(root: Path) -> dict:
    from .netcdf_compare import compare_netcdf
    from .scientific_feedback import paired_feedback
    root = root.resolve()
    reference = Path(json.loads((root / 'pilot.json').read_text())['reference'])
    reports, costs, feedback, errors = [], [], [], []
    for cycle_id, hour in zip(CYCLES, ('00', '06')):
        base = Path('work/jedi') / cycle_id
        products = [base / f'Data/states/mpas.3dfgat.2025-09-01_{hour}.00.00.nc']
        products += [base / f'Data/os/obsout_3dvar_{kind}.nc4' for kind in ('sondes', 'sfc', 'gnssroref')]
        for relative in products:
            try:
                report = compare_netcdf(reference / relative, root / relative)
                reports.append({'product': str(relative), 'equivalent': report.equivalent,
                                'variables_compared': report.variables_compared,
                                'differences': report.differences + report.data_differences})
            except (OSError, ValueError, RuntimeError) as error:
                errors.append(f'{relative}: {error}')
        try:
            relative = base / 'jedi.stdout.log'
            left, right = _costs(reference / relative), _costs(root / relative)
            costs.append({'cycle': cycle_id, 'equal': left == right, 'reference': left, 'candidate': right})
            relative = base / 'Data/os/obsout_3dvar_sondes.nc4'
            left, right = paired_feedback(reference / relative, 'airTemperature'), paired_feedback(root / relative, 'airTemperature')
            feedback.append({'cycle': cycle_id, 'equal': left == right, 'reference': left, 'candidate': right})
        except (OSError, ValueError, RuntimeError) as error:
            errors.append(f'{cycle_id}: {error}')
    for hour in ('03', '06'):
        relative = Path('work/mpas') / CYCLES[0] / f'mpasout.2025-09-01_{hour}.00.00.nc'
        try:
            report = compare_netcdf(reference / relative, root / relative)
            reports.append({'product': str(relative), 'equivalent': report.equivalent,
                            'variables_compared': report.variables_compared,
                            'differences': report.differences + report.data_differences})
        except (OSError, ValueError, RuntimeError) as error:
            errors.append(f'{relative}: {error}')
    passed = (not errors and len(reports) == 10 and len(costs) == len(feedback) == 2
              and all(r['equivalent'] and r['variables_compared'] > 0 for r in reports)
              and all(c['equal'] for c in costs + feedback))
    result = {'passed': passed, 'scope': 'exact numerical replay of short pilot only',
              'rtol': 0, 'atol': 0, 'ignored_root_attributes': ['file_id'],
              'products': reports, 'costs': costs, 'paired_sondes': feedback, 'errors': errors}
    (root / 'comparison.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    generate = sub.add_parser('generate')
    generate.add_argument('reference', type=Path)
    generate.add_argument('destination', type=Path)
    for name in ('preflight', 'compare'):
        sub.add_parser(name).add_argument('case', type=Path)
    args = parser.parse_args()
    if args.action == 'generate':
        generate_pilot(args.reference, args.destination)
        print(f'Prepared {args.destination}; no scientific program executed.')
        return 0
    result = preflight(args.case) if args.action == 'preflight' else compare_pilot(args.case)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result.get('passed', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
