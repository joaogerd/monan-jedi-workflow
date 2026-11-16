"""Create the installed, fixed September 2025 first-experiment recipe.

This is case creation only. Scientific execution remains in the domain apps.
"""
import argparse
from importlib.resources import files
from pathlib import Path
import shlex
import shutil
import re
import sysconfig
import yaml


def write(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def create_experiment(destination, *, pbs_queue='pesqmidi', pbs_walltime='01:00:00', runtime_bin=None):
    # Site policy documented in mpas-bmatrix-global/docs/jaci-operational-guide.md.
    # User should recheck the scheduler's live limits before submitting.
    queue_limits = {'pesqmini': 30, 'pesqmidi': 120, 'pesqhigh': 360,
                    'pesqextra': 480, 'oper': 480, 'preoper': 480}
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', pbs_queue):
        raise ValueError('PBS queue must be a simple queue name')
    match = re.fullmatch(r'(\d{1,3}):([0-5]\d):([0-5]\d)', pbs_walltime)
    if not match:
        raise ValueError('PBS walltime must use HH:MM:SS')
    minutes = int(match[1]) * 60 + int(match[2]) + int(match[3]) / 60
    if minutes <= 0:
        raise ValueError('PBS walltime must be positive')
    if pbs_queue in queue_limits and minutes > queue_limits[pbs_queue]:
        raise ValueError(f'PBS queue {pbs_queue} has a documented walltime limit of '
                         f'{queue_limits[pbs_queue]} minutes on JACI; requested {pbs_walltime}')
    runtime_bin = Path(runtime_bin or sysconfig.get_path('scripts')).expanduser().resolve()
    if runtime_bin.parts[:2] in {('/', 'home'), ('/', 'home2')}:
        raise ValueError(f'Python runtime is in HOME and may not be visible on JACI compute nodes: {runtime_bin}. Use --runtime-bin with a shared environment in /p.')
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
    # One site runtime wrapper is invoked by each independently submitted PBS task.
    # This does not create an enclosing PBS job or initiate scheduler submissions.
    worker = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'MONAN_RUNTIME_BIN='+shlex.quote(str(runtime_bin)),
        'if [[ ! -d "$MONAN_RUNTIME_BIN" ]]; then',
        '  echo "[FALHA] Ambiente Python nao visivel no compute node: $MONAN_RUNTIME_BIN" >&2',
        '  echo "O ambiente deve estar em /p (JACI); nao use HOME." >&2',
        '  exit 127',
        'fi',
        'export PATH="$MONAN_RUNTIME_BIN:$PATH"',
        'for app in python monan-jedi-workflow obs jedi mpas; do',
        '  if [[ ! -x "$MONAN_RUNTIME_BIN/$app" ]]; then',
        '    echo "[FALHA] Executavel $app ausente em $MONAN_RUNTIME_BIN" >&2',
        '    exit 127',
        '  fi',
        'done',
        '"$MONAN_RUNTIME_BIN/python" -c "import monan_jedi_workflow" || {',
        '  echo "[FALHA] Pacote monan_jedi_workflow indisponivel no Python do worker" >&2',
        '  exit 127',
        '}',
        'exec "$@"',
    ]
    (root / 'run-worker.sh').write_text('\\n'.join(worker)+'\\n')
    # Each stage is an individual simpleWorkflow task; PBS is requested only
    # by each declared scientific run task, never by the full experiment.
    initialization_cycle = '2025-08-31T18:00:00Z'
    first_cycle = '2025-09-01T00:00:00Z'
    last_cycle = '2025-09-01T06:00:00Z'
    campaign = {
        'schema_version': 1,
        'name': 'reference-20250901-two-analyses',
        'experiment': './experiment.yaml',
        'calendar': {
            'start': first_cycle, 'end': last_cycle,
            'interval': 'PT6H', 'end_inclusive': True,
        },
        'initialization': [
            {'operation': 'wps', 'cycle': initialization_cycle, 'experiment': './init.yaml'},
            {'operation': 'mpas.init', 'cycle': initialization_cycle, 'experiment': './init.yaml'},
            {'operation': 'mpas', 'cycle': initialization_cycle,
             'experiment': './initialization.yaml'},
        ],
        'operations': ['obs.convert', 'jedi', 'mpas'],
        'last_cycle': {'forecast': False},
        'output': './workflow.yaml',
    }
    write(root / 'campaign.yaml', campaign)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--pbs-queue', default='pesqmidi', help='PBS queue for the entire initial case (default: pesqmidi)')
    parser.add_argument('--pbs-walltime', default='01:00:00', help='Walltime HH:MM:SS (default: 01:00:00)')
    parser.add_argument('--runtime-bin', type=Path, help='Directory with Python and installed CLI entry points, visible on compute nodes (default: current Python scripts directory)')
    args=parser.parse_args()
    try:
        create_experiment(args.destination, pbs_queue=args.pbs_queue, pbs_walltime=args.pbs_walltime, runtime_bin=args.runtime_bin)
    except FileExistsError:
        root = args.destination.expanduser().resolve()
        parser.exit(
            2,
            f"\n[AVISO] O diretorio de destino ja existe:\n"
            f"  {root}\n\n"
            "Nenhum arquivo foi alterado. Para preservar experimentos anteriores,\n"
            "o pre-configurador nao sobrescreve diretorios existentes.\n\n"
            "O que fazer:\n"
            "  1. Para continuar um experimento ja criado, entre no diretorio existente.\n"
            "  2. Para criar outro experimento, informe um NOVO caminho que ainda nao exista.\n"
            "     Exemplo: export NEW_CASE=\""
            f"{root}-v2"
            "\"\n"
            "     Depois: python -m monan_jedi_workflow.experiment_start \"$NEW_CASE\"\n\n",
        )
    except ValueError as error:
        parser.exit(2, f'[ERRO DE CONFIGURACAO] {error}\nVerifique os limites atuais das filas com qstat -Qf no JACI.\n')
    print(f'[OK] Experimento configurado em: {args.destination.resolve()}')
    print('Proximo passo: campaign check campaign.yaml; campaign export campaign.yaml --engine simpleworkflow; swf validate workflow.yaml; swf run workflow.yaml --ui plain.')


if __name__=='__main__':
    main()
