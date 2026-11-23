"""Create an independent, date-configurable two-analysis reference experiment.

This is case creation only. Scientific execution remains in the domain apps.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path
import shlex
import shutil
import re
import sysconfig
import yaml
from .experiment_environment import render_environment, load_project_site


def write(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _utc_start(value, step_hours=6):
    """Validate an aligned UTC analysis time for the selected hourly interval."""
    if isinstance(value, datetime):
        start = value
    elif isinstance(value, str):
        try:
            start = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        except ValueError as error:
            raise ValueError(
                '--start must be UTC YYYY-MM-DDTHH:MM:SSZ, e.g. 2024-02-29T00:00:00Z'
            ) from error
    else:
        raise ValueError('--start must be a UTC date/time string')
    if start.tzinfo is None or start.utcoffset() != timedelta(0):
        raise ValueError('--start must have UTC timezone')
    if not isinstance(step_hours, int) or step_hours < 1 or 24 % step_hours:
        raise ValueError('cycle hours must be a positive divisor of 24')
    if start.hour % step_hours or start.minute or start.second or start.microsecond:
        raise ValueError(f'--start must align to PT{step_hours}H UTC cycles')
    return start


def _cycle(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def _cycle_id(dt):
    return dt.strftime('%Y%m%dT%H%M%SZ')


def _mpas_file_time(dt):
    return dt.strftime('%Y-%m-%d_%H.%M.%S')


def _duration(value, step_hours=6):
    """Parse whole-hour ISO duration, either PTnH or PnD."""
    match = re.fullmatch(r'P([1-9][0-9]*)D|PT([1-9][0-9]*)H', str(value))
    if not match:
        raise ValueError('duration must be PnD or PTnH, e.g. P7D or PT6H')
    hours = int(match[1]) * 24 if match[1] else int(match[2])
    if hours % step_hours:
        raise ValueError(f'PT{step_hours}H recipe requires duration in multiples of {step_hours} hours')
    return timedelta(hours=hours)


def create_experiment(destination, *, pbs_queue='pesqmidi', pbs_walltime='01:00:00', runtime_bin=None, start='2025-09-01T00:00:00Z', site_config=None, workspace=None, recipe_source=None, settings=None):
    settings = settings or {}
    interval = settings.get('cycle', 'PT6H')
    if not re.fullmatch(r'PT[1-9][0-9]*H', interval):
        raise ValueError('Invalid hourly cycle interval')
    step_hours = int(interval[2:-1])
    first_analysis = _utc_start(start, step_hours=step_hours)
    profile = settings.get('profile', {})
    offset_hours = profile.get('background_offset_hours', 3)
    if not isinstance(offset_hours, int) or not (0 < offset_hours < step_hours):
        raise ValueError('Invalid background_offset_hours in recipe')
    mesh_id = profile.get('mesh_id', 'x1.10242')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', mesh_id):
        raise ValueError('Invalid mesh_id in recipe profile')
    span = _duration(settings.get('duration', interval), step_hours=step_hours)
    final_analysis = first_analysis + span
    second_analysis = first_analysis + timedelta(hours=step_hours)
    initialization_time = first_analysis - timedelta(hours=step_hours)
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
    # Python runs on the login node. A HOME Conda runtime is valid for the
    # controller; compute nodes receive only native scientific PBS scripts.
    root = Path(destination).resolve()
    if root.exists():
        raise FileExistsError(f'Choose a new experiment directory: {root}')
    site_source, site_profile = load_project_site(
        root, site_config=site_config, configuration_workspace=workspace
    )
    recipe = Path(recipe_source) if recipe_source is not None else Path(str(files('monan_jedi_workflow').joinpath('catalog/reference-20250901')))
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
            # The first-cycle switch controls initial vs cycling background
            # selection; keeping the catalog's September date here silently
            # breaks every other experiment period.
            cfg.setdefault('cycle', {})['first_cycle'] = _cycle(first_analysis)
            cfg['run_dir'] = str(root / 'work/jedi/{cycle_id}')
            for field in ('source', 'initial_source'):
                cfg['background'][field] = str(root / 'work/background/{cycle_id}/trajectory.nc')
            cfg['analysis_base_state']['source'] = str(root / 'work/background/{cycle_id}/state.nc')
            for link in cfg['links']:
                if link['source'].startswith('work/obs/'):
                    link['source'] = str(root / link['source'])
        elif key == 'mpas':
            cfg['pbs']['queue'] = pbs_queue
            cfg['pbs']['walltime'] = pbs_walltime
            cfg['run_dir'] = str(root / ('work/initialization/mpas/{cycle_id}' if initial else 'work/mpas/{cycle_id}'))
            if initial:
                for link in cfg['links']:
                    if 'initialization/work/mpas-init/' in link['source']:
                        link['source'] = str(root / f'work/mpas-init/{{cycle_id}}/{mesh_id}.init.{{mpas_file_time}}.nc')
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
    # Validate scientific timing before modifying the copied configs.
    jedi_contract = yaml.safe_load((science / 'jedi.yaml').read_text())['jedi']['cycle']
    if (jedi_contract.get('step_hours') != step_hours
            or jedi_contract.get('background_offset_hours') != -offset_hours
            or jedi_contract.get('window_hours') != step_hours):
        raise ValueError('JEDI scientific timing does not match selected recipe cycle')
    for mpas_file in (science / 'mpas.yaml', science / 'initialization/mpas.yaml'):
        mpas_contract = yaml.safe_load(mpas_file.read_text())['mpas']
        if (mpas_contract.get('lead_hours') != step_hours
                or mpas_contract['forecast_contract'].get('run_hours') != step_hours
                or mpas_contract['forecast_contract'].get('da_state_interval_hours') != offset_hours):
            raise ValueError(f'MPAS forecast timing contract mismatch: {mpas_file}')
    # Restore the working main-branch site/runtime contract to all native PBS
    # stages. The original site's Python ABI check is disabled: no Python
    # interpreter is needed on compute nodes.
    site_file = science / 'site.yaml'
    site_document = (
        {key: value for key, value in site_profile.items()
         if key in {'site', 'stack', 'jedi', 'mpi', 'runtime'}}
        if site_profile else {
            'site': {'name': 'jaci'},
            'stack': {'load': True, 'root': '${STACK_ROOT}'},
            'jedi': {'install_root': '${MONAN_JEDI_INSTALL_ROOT}'},
            'runtime': {'unload_anaconda': True, 'validate_python': False},
        }
    )
    # Python is a login-side controller; the native scientific PBS job must
    # not require a Conda interpreter on the compute node.
    site_document['runtime'] = {
        **site_document.get('runtime', {}),
        'validate_python': False,
    }
    write(site_file, site_document)
    for stage_file in (
        science / 'jedi.yaml',
        science / 'mpas.yaml',
        science / 'initialization/mpas.yaml',
        science / 'initialization/mpas_init.yaml',
    ):
        doc = yaml.safe_load(stage_file.read_text())
        section = next(iter(doc.values()))
        section['pbs']['site_config'] = str(site_file)
        write(stage_file, doc)
    # Scientific WPS work is run by the WPS Python app on login, which submits
    # a native-only PBS job containing link_grib/ungrib.
    wps_file = science / 'initialization/wps.yaml'
    wps_doc = yaml.safe_load(wps_file.read_text())
    wps_doc['wps']['pbs'] = {
        'queue': 'pesqmini', 'select': 1, 'ncpus': 1,
        'mpiprocs': 1, 'walltime': '00:30:00',
        'site_config': str(site_file),
    }
    write(wps_file, wps_doc)
    # Obs2IODA is also an HPC operation; execute conversion in its own PBS job.
    obs_file = science / 'obs2ioda.yaml'
    obs_doc = yaml.safe_load(obs_file.read_text())
    obs_doc['obs2ioda']['pbs'] = {
        'queue': 'pesqmidi', 'select': 1, 'ncpus': 1,
        'mpiprocs': 1, 'walltime': '01:00:00',
        'site_config': str(site_file),
    }
    write(obs_file, obs_doc)
    site = {'execution': {'mode': 'pbs'}}
    principal = {'schema_version': 1, 'experiment': {'name': 'first-' + first_analysis.strftime('%Y%m%d%H'), 'destination': str(root)},
                 'site': site, 'jedi': './science/jedi.yaml', 'mpas': './science/mpas.yaml',
                 'observations': './science/obs2ioda.yaml', 'cycle': {'interval':interval}}
    write(root / 'experiment.yaml', principal)
    write(root / 'initialization.yaml', {**principal, 'mpas': './science/initialization/mpas.yaml'})
    # init has its own principal, because native mpas/init and forecast configurations are distinct.
    write(root / 'init.yaml', {**principal, 'mpas': './science/initialization/mpas_init.yaml'})
    # Each first analysis consumes the 3 h and 6 h outputs of the
    # initialization forecast; the second consumes the cycling forecast.
    # Derive all dates, including month/year/leap transitions, from --start.
    step_seconds = step_hours * 3600
    analyses = [first_analysis + timedelta(hours=step_hours * index)
                for index in range(int(span.total_seconds() // step_seconds) + 1)]
    for index, analysis in enumerate(analyses):
        forecast_start = initialization_time if index == 0 else analyses[index - 1]
        forecast_dir = 'work/initialization/mpas' if index == 0 else 'work/mpas'
        folder = root / 'work/background' / _cycle_id(analysis)
        folder.mkdir(parents=True)
        forecast = root / forecast_dir / _cycle_id(forecast_start)
        (folder / 'trajectory.nc').symlink_to(
            forecast / ('mpasout.' + _mpas_file_time(analysis - timedelta(hours=offset_hours)) + '.nc')
        )
        (folder / 'state.nc').symlink_to(
            forecast / ('mpasout.' + _mpas_file_time(analysis) + '.nc')
        )
    (root / 'environment.sh').write_text(render_environment(root, site_profile=site_profile))
    # Legacy optional worker wrapper kept for compatibility. The exported
    # simpleWorkflow DAG now runs native stage apps on the login node and does
    # not invoke this wrapper from PBS.
    worker = [
        '#!/usr/bin/env bash',
        'set -euo pipefail',
        'source '+shlex.quote(str(root / 'environment.sh')),
        'if [[ -n "${MONAN_JACI_LOADER:-}" ]]; then',
        '  if [[ ! -f "$MONAN_JACI_LOADER" ]]; then',
        '    echo "[FALHA] Carregador JACI nao existe: $MONAN_JACI_LOADER" >&2',
        '    exit 127',
        '  fi',
        '  _monan_requested_stack="$STACK_ROOT"',
        '  source "$MONAN_JACI_LOADER"',
        '  if [[ "$STACK_ROOT" != "$_monan_requested_stack" ]]; then',
        '    echo "[FALHA] Carregador JACI alterou STACK_ROOT. O stack do job deve coincidir com a receita." >&2',
        '    echo "  esperado: $_monan_requested_stack" >&2',
        '    echo "  carregado: $STACK_ROOT" >&2',
        '    exit 2',
        '  fi',
        '  unset _monan_requested_stack',
        'fi',
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
    (root / 'run-worker.sh').write_text('\n'.join(worker)+'\n')
    # Each stage is an individual simpleWorkflow task; PBS is requested only
    # by each declared scientific run task, never by the full experiment.
    initialization_cycle = _cycle(initialization_time)
    first_cycle = _cycle(first_analysis)
    last_cycle = _cycle(final_analysis)
    campaign = {
        'schema_version': 1,
        'name': 'reference-' + first_analysis.strftime('%Y%m%d%H') + '-' + str(len(analyses)) + '-analyses',
        'experiment': './experiment.yaml',
        'calendar': {
            'start': first_cycle, 'end': last_cycle,
            'interval': interval, 'end_inclusive': True,
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
    # Reproducibility: snapshot settings into the new case.
    (root / 'recipe-lock.json').write_text(json.dumps(
        {'recipe': settings.get('recipe', 'legacy-reference'),
         'resolved': settings, 'source': str(recipe)}, indent=2, sort_keys=True
    ) + '\\n')


def suggest_available_dates(*, input_root, gfs_root, exclude='2025-09-01T00:00:00Z', limit=6):
    """Find real two-cycle dates using the reference recipe's raw input layout.

    Pure filesystem discovery: no synthetic data, no download and no job
    submission. Candidate dates require PREPNR and GNSSRO at both analyses
    plus one GFS GRIB at T-6h. The scientific work still needs validation.
    """
    input_root = Path(input_root)
    gfs_root = Path(gfs_root)
    source = input_root / 'observations/prepnr'
    if not source.is_dir() or not gfs_root.is_dir():
        return []
    stamps = set()
    for path in source.glob('*/prepbufr.gdas.*.nr'):
        if not path.is_file() or path.stat().st_size == 0:
            continue
        match = re.fullmatch(r'prepbufr\.gdas\.(\d{10})\.nr', path.name)
        if match:
            stamps.add(match[1])
    results = []
    for stamp in sorted(stamps):
        try:
            first = datetime.strptime(stamp, '%Y%m%d%H').replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if first.hour not in (0, 6, 12, 18) or first.date() == _utc_start(exclude).date():
            continue
        second = first + timedelta(hours=6)
        initial = first - timedelta(hours=6)
        if second.strftime('%Y%m%d%H') not in stamps:
            continue
        obs_ready = all(
            (input_root / 'observations/gpsro' / dt.strftime('%Y')
             / f"gdas.gpsro.t{dt:%H}z.{dt:%Y%m%d}.bufr").is_file()
            for dt in (first, second)
        )
        gfs_path = (
            gfs_root / initial.strftime('%Y%m%d%H')
            / f"gfs.t{initial:%H}z.pgrb2.0p25.f000"
        )
        if obs_ready and gfs_path.is_file() and gfs_path.stat().st_size:
            results.append(_cycle(first))
            if len(results) >= limit:
                break
    return results


def check_date_inputs(destination):
    """Read-only availability gate for the selected two-cycle scientific period.

    Reject a new run early when its date-specific raw GFS/PREPNR/GNSSRO files
    are missing. Never substitute another date, download, or reuse products.
    """
    from .wps_stage import load_wps_run
    from .obs2ioda_stage import load_obs2ioda_run, _build_plan
    from .stage_config import resolve_path

    root = Path(destination).expanduser().resolve()
    campaign_file = root / 'campaign.yaml'
    if not campaign_file.is_file():
        raise FileNotFoundError(f'Campaign file missing: {campaign_file}')
    campaign = yaml.safe_load(campaign_file.read_text())
    start = _utc_start(campaign['calendar']['start'])
    last = _utc_start(campaign['calendar']['end'])
    if last <= start or (last - start).total_seconds() % 21600:
        raise ValueError('Reference input preflight requires a positive six-hour cycle range')
    initial = _cycle(start - timedelta(hours=6))
    wps = load_wps_run(root / 'science/initialization', initial)
    raw = resolve_path(
        wps.config['acquisition']['source'],
        config_dir=wps.config_dir, context=wps.context,
        label='wps.acquisition.source',
    )
    required = [('GFS initialization ' + initial, raw)]
    cycles = [start + timedelta(hours=6 * idx)
              for idx in range(int((last - start).total_seconds() // 21600) + 1)]
    for analysis in cycles:
        cycle = _cycle(analysis)
        obs = load_obs2ioda_run(root / 'science', cycle)
        for converter in _build_plan(obs)['converters']:
            for source in converter['inputs']:
                required.append((f"{converter['name']} {cycle}", Path(source)))
    seen = set()
    results = []
    for label, path in required:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        available = path.is_file() and path.stat().st_size > 0
        results.append((label, path, available))
    return results


def configure_existing_environment(destination):
    """Add only a missing environment to an existing generated campaign."""
    root = Path(destination).resolve()
    worker = root / 'run-worker.sh'
    campaign = root / 'campaign.yaml'
    if not campaign.is_file() or not worker.is_file():
        raise ValueError('Existing destination is not a generated simpleWorkflow experiment')
    env_file = root / 'environment.sh'
    if env_file.exists():
        raise FileExistsError(f'Environment configuration already exists: {env_file}')
    worker_source = 'source ' + shlex.quote(str(env_file))
    lines = worker.read_text().splitlines()
    if worker_source not in lines:
        try:
            index = lines.index('set -euo pipefail')
        except ValueError as error:
            raise ValueError('Worker header has changed; no file was modified') from error
        lines.insert(index + 1, worker_source)
    if '  source "$MONAN_JACI_LOADER"' not in lines:
        index = lines.index(worker_source)
        lines[index + 1:index + 1] = [
            'if [[ -n "${MONAN_JACI_LOADER:-}" ]]; then',
            '  if [[ ! -f "$MONAN_JACI_LOADER" ]]; then',
            '    echo "[FALHA] Carregador JACI nao existe: $MONAN_JACI_LOADER" >&2',
            '    exit 127',
            '  fi',
            '  _monan_requested_stack="$STACK_ROOT"',
        '  source "$MONAN_JACI_LOADER"',
        '  if [[ "$STACK_ROOT" != "$_monan_requested_stack" ]]; then',
        '    echo "[FALHA] Carregador JACI alterou STACK_ROOT. O stack do job deve coincidir com a receita." >&2',
        '    echo "  esperado: $_monan_requested_stack" >&2',
        '    echo "  carregado: $STACK_ROOT" >&2',
        '    exit 2',
        '  fi',
        '  unset _monan_requested_stack',
            'fi',
        ]
    # Validate script structure before changing any existing user file.
    env_file.write_text(render_environment(root))
    worker.write_text('\n'.join(lines) + '\n')
    return env_file


def upgrade_existing_login_execution(destination):
    """Create a new orchestration entrypoint without overwriting old workflow.

    For reference cases made before the login-only architecture:
    add WPS native PBS configuration (saving its previous YAML), and export
    a separate campaign filename, leaving old campaign/workflow untouched.
    """
    root = Path(destination).resolve()
    original_campaign = root / 'campaign.yaml'
    original_wps = root / 'science/initialization/wps.yaml'
    if not original_campaign.is_file() or not original_wps.is_file():
        raise ValueError('Expected an existing generated first experiment, not a directory without the reference recipe')
    output = root / 'campaign-login.yaml'
    if output.exists():
        raise FileExistsError(f'Login campaign already exists: {output}')
    doc = yaml.safe_load(original_wps.read_text())
    if not isinstance(doc, dict) or not isinstance(doc.get('wps'), dict):
        raise ValueError('Invalid existing WPS configuration')
    if doc['wps'].get('pbs'):
        # No modification to a user-configured PBS resource block.
        pass
    else:
        backup = original_wps.with_suffix('.yaml.before-login')
        if backup.exists():
            raise FileExistsError(f'WPS backup already exists: {backup}')
        shutil.copy2(original_wps, backup)
        doc['wps']['pbs'] = {
            'queue': 'pesqmini', 'select': 1, 'ncpus': 1,
            'mpiprocs': 1, 'walltime': '00:30:00',
        }
        write(original_wps, doc)
    campaign = yaml.safe_load(original_campaign.read_text())
    if not isinstance(campaign, dict):
        raise ValueError('Invalid campaign YAML')
    campaign['output'] = './workflow-login.yaml'
    write(output, campaign)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--suggest-dates', action='store_true',
                        help='List other complete two-cycle dates from the existing raw data inventory')
    parser.add_argument('--check-inputs', action='store_true',
                        help='Read-only check of GFS and 2-cycle PREPNR/GNSSRO files in an existing case')
    parser.add_argument('--start', default='2025-09-01T00:00:00Z',
                        help='First analysis (UTC), YYYY-MM-DDTHH:MM:SSZ; two 6-hour cycles')
    parser.add_argument('--site', type=Path, help='Persistent YAML site profile (or workspace/site.yaml if present)')
    parser.add_argument('--pbs-queue', default='pesqmidi', help='PBS queue for the entire initial case (default: pesqmidi)')
    parser.add_argument('--pbs-walltime', default='01:00:00', help='Walltime HH:MM:SS (default: 01:00:00)')
    parser.add_argument('--upgrade-existing', action='store_true', help='Create a new login-side campaign for existing experiments without overwriting old exported workflow')
    parser.add_argument('--configure-existing', action='store_true', help='Safely add missing environment.sh to an existing generated campaign, without recreating scientific files')
    parser.add_argument('--runtime-bin', type=Path, help='Python CLI directory for optional legacy worker wrapper; not used by login-side simpleWorkflow tasks')
    args=parser.parse_args()
    try:
        if args.suggest_dates:
            import os
            input_root = os.environ.get('MONAN_INPUT_ROOT')
            gfs_root = os.environ.get('MONAN_GFS_ROOT')
            if not input_root or not gfs_root:
                parser.exit(2, '[CONFIGURACAO] Source environment.sh first to define MONAN_INPUT_ROOT and MONAN_GFS_ROOT.\\n')
            dates = suggest_available_dates(input_root=input_root, gfs_root=gfs_root)
            for day in dates:
                print('[AVAILABLE] ' + day)
            if not dates:
                parser.exit(2, '[MISSING] No other 2-cycle period has PREPNR, GPSRO and initial GFS available. '
                           'Acquire date-specific inputs before a scientific portability test.\\n')
            return
        if args.check_inputs:
            results = check_date_inputs(args.destination)
            for label, path, available in results:
                print(f'[{"OK" if available else "MISSING"}] {label}: {path}')
            missing = sum(not present for _, _, present in results)
            if missing:
                parser.exit(2, f'[FALHA] {missing} entrada(s) indisponivel(is) para o periodo escolhido. '
                           'Nao submeta jobs. Escolha data com cobertura completa ou obtenha os dados correspondentes.\\n')
            print(f'[OK] Todas as {len(results)} entradas verificadas para as duas analises.')
            return
        if args.upgrade_existing:
            output = upgrade_existing_login_execution(args.destination)
            print(f'[OK] Login-side orchestration campaign: {output}')
            print('Proximo passo: source ./environment.sh; campaign check campaign-login.yaml; campaign export campaign-login.yaml --engine simpleworkflow; swf validate workflow-login.yaml; swf plan workflow-login.yaml.')
            return
        if args.configure_existing:
            env_path = configure_existing_environment(args.destination)
            print(f'[OK] Ambiente gerado: {env_path}')
            print('Proximo passo: cd '+str(args.destination.resolve())+'; source ./environment.sh')
            return
        create_experiment(args.destination, pbs_queue=args.pbs_queue, pbs_walltime=args.pbs_walltime, runtime_bin=args.runtime_bin, start=args.start, site_config=args.site)
    except FileExistsError as error:
        if args.configure_existing:
            parser.exit(2, f'[AVISO] {error}\\nNenhum arquivo foi modificado.\\n')
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
        parser.exit(2, f'[ERRO DE CONFIGURACAO] {error}\nVerifique o ambiente Python compartilhado em /p, as opcoes do comando e, para recursos PBS, qstat -Qf na JACI.\n')
    print(f'[OK] Experimento configurado em: {args.destination.resolve()}')
    print('Proximo passo: cd '+str(args.destination.resolve())+'; source ./environment.sh; campaign check campaign.yaml; campaign export campaign.yaml --engine simpleworkflow; swf validate workflow.yaml; swf plan workflow.yaml.')


if __name__=='__main__':
    main()
