"""Create the installed, fixed September 2025 first-experiment recipe.

This is case creation only. Scientific execution remains in the domain apps.
"""
import argparse
from importlib.resources import files
from pathlib import Path
import shlex
import shutil
import yaml


def write(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def create_experiment(destination):
    root = Path(destination).resolve()
    if root.exists():
        raise FileExistsError(f'Choose a new experiment directory: {root}')
    recipe = Path(str(files('monan_jedi_workflow').joinpath('catalog/reference-20250901')))
    shutil.copytree(recipe, root / 'science')
    science = root / 'science'
    for relative, key in [('jedi.yaml','jedi'), ('mpas.yaml','mpas'), ('obs2ioda.yaml','obs2ioda'),
                          ('initialization/mpas.yaml','mpas'), ('initialization/mpas_init.yaml','mpas_init'),
                          ('initialization/wps.yaml','wps')]:
        path = science / relative
        doc = yaml.safe_load(path.read_text()); cfg = doc[key]
        cfg['variables'] = {'experiment_root': str(root), 'configuration_root': str(path.parent), **cfg.get('variables', {})}
        initial = relative.startswith('initialization/')
        if key == 'jedi':
            cfg['run_dir'] = str(root / 'work/jedi/{cycle_id}')
            for field in ('source', 'initial_source'):
                cfg['background'][field] = str(root / 'work/background/{cycle_id}/trajectory.nc')
            cfg['analysis_base_state']['source'] = str(root / 'work/background/{cycle_id}/state.nc')
            for link in cfg['links']:
                if link['source'].startswith('work/obs/'):
                    link['source'] = str(root / link['source'])
        elif key == 'mpas':
            cfg['run_dir'] = str(root / ('work/initialization/mpas/{cycle_id}' if initial else 'work/mpas/{cycle_id}'))
            if initial:
                for link in cfg['links']:
                    if 'initialization/work/mpas-init/' in link['source']:
                        link['source'] = str(root / 'work/mpas-init/{cycle_id}/x1.10242.init.{mpas_file_time}.nc')
                for template in cfg['templates']:
                    template['source'] = str(science / 'templates' / Path(template['source']).name)
        elif key == 'mpas_init':
            cfg['run_dir'] = str(root / 'work/mpas-init/{cycle_id}')
            for link in cfg['links']:
                if link['source'].startswith('work/wps/'):
                    link['source'] = str(root / link['source'])
            cfg['validation']['required_outputs'] = [str(root / p) for p in cfg['validation']['required_outputs']]
        elif key == 'wps':
            cfg['work_dir'] = str(root / 'work/wps/{cycle_id}')
            cfg['validation']['required_outputs'] = [str(root / p) for p in cfg['validation']['required_outputs']]
        else:
            cfg['work_dir'] = str(root / 'work/obs/{cycle_yyyymmddhh}')
            for name, runner in [('prepbufr_runner','run_prepbufr.sh'),('gpsro_runner','run_gpsro.sh')]:
                cfg['variables'][name] = str(science / 'runners' / runner)
        write(path, doc)
    site = {'execution': {'mode': 'pbs'}}
    principal = {'schema_version': 1, 'experiment': {'name': 'first-20250901', 'destination': str(root)},
                 'site': site, 'jedi': './science/jedi.yaml', 'mpas': './science/mpas.yaml',
                 'observations': './science/obs2ioda.yaml', 'cycle': {'interval':'PT6H'}}
    write(root / 'experiment.yaml', principal)
    write(root / 'initialization.yaml', {**principal, 'mpas': './science/initialization/mpas.yaml'})
    # init has its own principal, because native mpas/init and forecast configurations are distinct.
    write(root / 'init.yaml', {**principal, 'mpas': './science/initialization/mpas_init.yaml'})
    for cid, parent, stamp in [('20250901T000000Z','work/initialization/mpas/20250831T180000Z','2025-08-31_21.00.00'),
                               ('20250901T060000Z','work/mpas/20250901T000000Z','2025-09-01_03.00.00')]:
        folder=root/'work/background'/cid;folder.mkdir(parents=True)
        (folder/'trajectory.nc').symlink_to(root/parent/f'mpasout.{stamp}.nc')
        valid='2025-09-01_00.00.00' if cid.endswith('000000Z') else '2025-09-01_06.00.00'
        (folder/'state.nc').symlink_to(root/parent/f'mpasout.{valid}.nc')
    lines=['#!/bin/bash','#PBS -N monan-first-case','#PBS -q pesqmidi',
           '#PBS -l select=1:ncpus=128:mpiprocs=128','#PBS -l walltime=06:00:00','#PBS -V',
           'set -euo pipefail', ': "${PBS_JOBID:?Submit with qsub}"',
           'cd '+shlex.quote(str(root)), 'exec >case.stdout.log 2>case.stderr.log']
    time='2025-08-31T18:00:00Z'
    for verb in ('prepare','run','validate'):
        lines.append(f'monan-jedi-workflow wps-{verb} science/initialization --cycle {time}')
    steps=[('mpas init','init.yaml',time),('mpas','initialization.yaml',time)]
    for time in ['2025-09-01T00:00:00Z','2025-09-01T06:00:00Z']:
        steps.extend([('obs convert','experiment.yaml',time),('jedi','experiment.yaml',time)])
        if 'T00:' in time:steps.append(('mpas','experiment.yaml',time))
    for app,config,time in steps:
        for verb in ('check','prepare','run','validate'):
            lines.append(f'{app} {verb} {config} --cycle {time}')
    (root/'run-case.pbs').write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    create_experiment(args.destination)
    print(f'Created {args.destination}. Configure input roots, then inspect/check before submitting run-case.pbs.')


if __name__=='__main__':
    main()
