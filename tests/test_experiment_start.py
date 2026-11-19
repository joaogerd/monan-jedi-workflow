from pathlib import Path
import subprocess
import sys
import pytest
import yaml
from monan_jedi_workflow.experiment_start import create_experiment


def test_installed_recipe_creates_independent_case(tmp_path):
    root = tmp_path / 'case'
    create_experiment(root)
    config = yaml.safe_load((root / 'science/jedi.yaml').read_text())['jedi']
    assert all('EDITAR' not in p.read_text() for p in root.rglob('*.yaml'))
    assert config['pbs']['mpiprocs'] == 128
    assert (root / 'science/templates/variational.yaml').is_file()
    first = root / 'work/background/20250901T000000Z/trajectory.nc'
    assert first.readlink() == root / 'work/initialization/mpas/20250831T180000Z/mpasout.2025-08-31_21.00.00.nc'
    assert not (root / 'run-case.pbs').exists()
    assert (root / 'run-worker.sh').is_file()
    assert (root / 'environment.sh').is_file()
    assert 'source ' + str(root / 'environment.sh') in (root / 'run-worker.sh').read_text()
    campaign = yaml.safe_load((root / 'campaign.yaml').read_text())
    assert [x['operation'] for x in campaign['initialization']] == ['wps', 'mpas.init', 'mpas']
    assert campaign['operations'] == ['obs.convert', 'jedi', 'mpas']
    assert campaign['last_cycle']['forecast'] is False
    with pytest.raises(FileExistsError):
        create_experiment(root)


def test_native_variable_dependencies_resolve_in_order(tmp_path, monkeypatch):
    from monan_jedi_workflow.stage_config import render_declared_variables
    from monan_jedi_workflow.cycle_context import parse_cycle_time
    monkeypatch.setenv('MONAN_JEDI_INSTALL_ROOT', '/test/install')
    monkeypatch.setenv('STACK_ROOT', '/test/stack')
    for name in ['INPUT', 'MESH', 'PHYSICS', 'BMATRIX', 'GFS', 'LIBFABRIC']:
        monkeypatch.setenv(f'MONAN_{name}_ROOT', '/test/'+name)
    monkeypatch.setattr('monan_jedi_workflow.stage_config.runtime_contract_context', lambda *a: {})
    root=tmp_path/'case';create_experiment(root)
    for file,key in [('science/mpas.yaml','mpas'),('science/obs2ioda.yaml','obs2ioda')]:
        cfg=yaml.safe_load((root/file).read_text())[key]
        resolved=render_declared_variables(cfg,parse_cycle_time('2025-09-01T00:00:00Z').render_context(),label=key)
        assert resolved['experiment_root']==str(root)


def test_cli_existing_destination_is_friendly_and_non_destructive(tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("do not modify")
    result = subprocess.run(
        [sys.executable, "-m", "monan_jedi_workflow.experiment_start", str(destination)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "[AVISO]" in result.stderr
    assert "ja existe" in result.stderr
    assert "Nenhum arquivo foi alterado" in result.stderr
    assert str(destination) in result.stderr
    assert marker.read_text() == "do not modify"


def test_generator_pbs_defaults_match_documented_jaci_queue(tmp_path):
    root = tmp_path / "pbs-default"
    create_experiment(root)
    campaign = yaml.safe_load((root / "campaign.yaml").read_text())
    assert campaign["calendar"]["interval"] == "PT6H"
    assert (root / "run-worker.sh").is_file()


@pytest.mark.parametrize("queue,walltime", [
    ("pesqmini", "00:31:00"),
    ("pesqmidi", "06:00:00"),
    ("pesqhigh", "06:01:00"),
])
def test_generator_rejects_documented_queue_limits_without_creating_case(tmp_path, queue, walltime):
    root = tmp_path / "invalid-pbs"
    with pytest.raises(ValueError, match="documented walltime limit"):
        create_experiment(root, pbs_queue=queue, pbs_walltime=walltime)
    assert not root.exists()


def test_generator_accepts_configured_valid_walltime(tmp_path):
    root = tmp_path / "short-pbs"
    create_experiment(root, pbs_queue="pesqmidi", pbs_walltime="01:45:00")
    assert (root / "campaign.yaml").is_file()
    assert not (root / "run-case.pbs").exists()


def test_generator_binds_runtime_commands_for_pbs(tmp_path):
    root = tmp_path / "runtime-case"
    create_experiment(root, runtime_bin=tmp_path / "conda-env/bin")
    script = (root / "run-worker.sh").read_text()
    assert "MONAN_RUNTIME_BIN=" in script
    assert str(tmp_path / "conda-env/bin") in script
    assert 'export PATH="$MONAN_RUNTIME_BIN:$PATH"' in script
    assert "monan-jedi-workflow obs jedi mpas" in script
    assert "Pacote monan_jedi_workflow indisponivel" in script


def test_reference_campaign_exports_login_apps_which_submit_native_pbs(tmp_path, monkeypatch):
    from dataclasses import replace
    from monan_jedi_workflow.domain_cli import parse_request
    from monan_jedi_workflow.platform_campaign import campaign_action
    # All external scientific inputs are paths, not needed for graph construction.
    for name in ('MONAN_JEDI_INSTALL', 'STACK', 'MONAN_INPUT', 'MONAN_MESH',
                 'MONAN_PHYSICS', 'MONAN_BMATRIX', 'MONAN_LIBFABRIC', 'MONAN_GFS'):
        monkeypatch.setenv(name + '_ROOT', str(tmp_path / name))
    root = tmp_path / 'case'
    create_experiment(root, runtime_bin=tmp_path / 'env/bin')
    request = parse_request('campaign', ['export', str(root / 'campaign.yaml')])
    report = campaign_action(request)
    assert report['cycles'] == 2
    workflow = yaml.safe_load((root / 'workflow.yaml').read_text())
    initial = workflow['initialization']['tasks']
    tasks = workflow['tasks']
    assert len(initial) == 9  # 3 WPS + 3 MPAS init + 3 MPAS initial
    assert len(tasks) == 15  # OBS 00Z, JEDI 00Z, MPAS 00Z, OBS 06Z, JEDI 06Z
    # simpleWorkflow runs the whole initialization phase before cycle tasks.
    # A cross-phase task-name dependency would be invalid in its separate engines.
    assert 'depends_on' not in tasks[0]
    assert initial[3]['depends_on'] == [initial[2]['name']]
    for task in [*initial, *tasks]:
        assert task['executor'] == 'local'
        assert 'pbs' not in task
        assert task['argv'][0] in {'wps', 'obs', 'mpas', 'jedi', 'diagnostic'}
        assert task['name'] != 'run-case'
    assert next(t for t in initial if t['name'] == 'init000_wps_run')['argv'][:3] == ['wps', 'run', str(root / 'science/initialization')]
    assert next(t for t in tasks if t['name'] == 'c00000_obs_convert_run')['argv'][:3] == ['obs', 'convert', 'run']


def test_environment_script_exports_and_checks_required_paths(tmp_path):
    from monan_jedi_workflow.experiment_environment import REQUIRED, render_environment
    import os
    env = {}
    for key in REQUIRED:
        folder = tmp_path / key
        folder.mkdir()
        env[key] = str(folder)
    script = tmp_path / 'environment.sh'
    script.write_text(render_environment(tmp_path / 'case', environ=env))
    result = subprocess.run(
        ['bash', '-c', 'set -e; source "$1"; '
         'test "$MONAN_JEDI_INSTALL_ROOT" = "$2"; '
         'test "$STACK_ROOT" = "$3"',
         'bash', str(script), env['MONAN_JEDI_INSTALL_ROOT'], env['STACK_ROOT']],
        capture_output=True, text=True, env={'PATH': os.environ['PATH']},
    )
    assert result.returncode == 0, result.stderr


def test_environment_script_reports_missing_paths_before_campaign(tmp_path):
    from monan_jedi_workflow.experiment_environment import REQUIRED, render_environment
    import os
    env = {key: str(tmp_path / key) for key in REQUIRED}
    script = tmp_path / 'environment.sh'
    script.write_text(render_environment(tmp_path / 'case', environ=env))
    result = subprocess.run(
        ['bash', '-c', 'source "$1"', 'bash', str(script)],
        capture_output=True, text=True, env={'PATH': os.environ['PATH']},
    )
    assert result.returncode == 2
    assert 'diretorio inexistente' in result.stderr
    assert 'MONAN_JEDI_INSTALL_ROOT' in result.stderr


def test_configure_existing_environment_preserves_scientific_case(tmp_path):
    from monan_jedi_workflow.experiment_start import configure_existing_environment
    root = tmp_path / 'case'
    create_experiment(root, runtime_bin=tmp_path / 'env/bin')
    env_file = root / 'environment.sh'
    env_file.unlink()
    worker = root / 'run-worker.sh'
    original = worker.read_text()
    worker.write_text(original.replace('source ' + str(env_file) + '\n', ''))
    previous = (root / 'science/jedi.yaml').read_bytes()
    configure_existing_environment(root)
    assert env_file.is_file()
    assert 'source ' + str(env_file) in worker.read_text()
    assert (root / 'science/jedi.yaml').read_bytes() == previous
    with pytest.raises(FileExistsError):
        configure_existing_environment(root)


@pytest.mark.parametrize('home_runtime', [
    '/home/user/.conda/envs/monan-jedi/bin',
    '/home2/user/.conda/envs/monan-jedi/bin',
    '/h2mnt/home/user/.conda/envs/monan-jedi/bin',
])
def test_generator_allows_login_home_python_runtime(tmp_path, home_runtime):
    root = tmp_path / 'case'
    create_experiment(root, runtime_bin=home_runtime)
    assert (root / 'campaign.yaml').is_file()
    assert not (root / 'run-case.pbs').exists()


@pytest.mark.parametrize('start,init,second,trajectory0,state0,trajectory1', [
    ('2024-02-29T00:00:00Z', '2024-02-28T18:00:00Z', '2024-02-29T06:00:00Z',
     '2024-02-28_21.00.00', '2024-02-29_00.00.00', '2024-02-29_03.00.00'),
    ('2023-01-01T00:00:00Z', '2022-12-31T18:00:00Z', '2023-01-01T06:00:00Z',
     '2022-12-31_21.00.00', '2023-01-01_00.00.00', '2023-01-01_03.00.00'),
    ('2026-11-16T18:00:00Z', '2026-11-16T12:00:00Z', '2026-11-17T00:00:00Z',
     '2026-11-16_15.00.00', '2026-11-16_18.00.00', '2026-11-16_21.00.00'),
])
def test_arbitrary_first_analysis_generates_correct_initialization_and_cycling(
    tmp_path, start, init, second, trajectory0, state0, trajectory1,
):
    from datetime import datetime
    root = tmp_path / ('case-' + start[:10])
    create_experiment(root, start=start)
    campaign = yaml.safe_load((root / 'campaign.yaml').read_text())
    assert campaign['calendar']['start'] == start
    assert campaign['calendar']['end'] == second
    jedi = yaml.safe_load((root / 'science/jedi.yaml').read_text())['jedi']
    assert jedi['cycle']['first_cycle'] == start
    assert len(campaign['initialization']) == 3
    assert all(step['cycle'] == init for step in campaign['initialization'])
    first_id = datetime.strptime(start, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y%m%dT%H%M%SZ')
    second_id = datetime.strptime(second, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y%m%dT%H%M%SZ')
    init_id = datetime.strptime(init, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y%m%dT%H%M%SZ')
    bg0 = root / 'work/background' / first_id
    bg1 = root / 'work/background' / second_id
    assert bg0.joinpath('trajectory.nc').readlink() == (
        root / 'work/initialization/mpas' / init_id / ('mpasout.' + trajectory0 + '.nc')
    )
    assert bg0.joinpath('state.nc').readlink() == (
        root / 'work/initialization/mpas' / init_id / ('mpasout.' + state0 + '.nc')
    )
    assert bg1.joinpath('trajectory.nc').readlink() == (
        root / 'work/mpas' / first_id / ('mpasout.' + trajectory1 + '.nc')
    )
    assert bg1.joinpath('state.nc').readlink() == (
        root / 'work/mpas' / first_id /
        ('mpasout.' + datetime.strptime(second, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d_%H.%M.%S') + '.nc')
    )
    assert yaml.safe_load((root / 'experiment.yaml').read_text())['experiment']['name'] != 'first-20250901'


@pytest.mark.parametrize('start', [
    '2025-02-29T00:00:00Z', # not a leap year
    '2025-09-01T03:00:00Z', # unsupported DA slot
    '2025-09-01', '2030-13-01T00:00:00Z',
])
def test_generator_rejects_invalid_start_without_creating_experiment(tmp_path, start):
    root = tmp_path / 'not-created'
    with pytest.raises(ValueError, match='--start'):
        create_experiment(root, start=start)
    assert not root.exists()


def test_cli_can_create_cross_year_case_from_start(tmp_path):
    dest = tmp_path / 'new-year'
    result = subprocess.run([
        sys.executable, '-m', 'monan_jedi_workflow.experiment_start',
        str(dest), '--start', '2023-01-01T00:00:00Z',
    ], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    campaign = yaml.safe_load((dest/'campaign.yaml').read_text())
    assert campaign['initialization'][0]['cycle'] == '2022-12-31T18:00:00Z'
    assert campaign['calendar']['start'] == '2023-01-01T00:00:00Z'


def test_date_input_preflight_requires_only_selected_cycle_files(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import monan_jedi_workflow.experiment_start as startmod
    from monan_jedi_workflow import wps_stage, obs2ioda_stage
    root = tmp_path / 'case'
    startmod.create_experiment(root, start='2024-02-29T00:00:00Z')
    raw_gfs = tmp_path / 'gfs' / '2024022818.grib2'
    raw_obs0 = tmp_path / 'obs' / '2024022900.bufr'
    raw_obs1 = tmp_path / 'obs' / '2024022906.bufr'
    runner = tmp_path / 'run_gpsro.sh'
    runner.write_text('runner')
    raw_gfs.parent.mkdir(parents=True)
    raw_obs0.parent.mkdir(parents=True)
    monkeypatch.setattr(wps_stage, 'load_wps_run', lambda *args: SimpleNamespace(
        config={'acquisition': {'source': str(raw_gfs)}},
        config_dir=tmp_path, context={},
    ))
    def load_obs(config_dir, cycle):
        assert cycle in {'2024-02-29T00:00:00Z', '2024-02-29T06:00:00Z'}
        return SimpleNamespace(cycle=cycle)
    monkeypatch.setattr(obs2ioda_stage, 'load_obs2ioda_run', load_obs)
    monkeypatch.setattr(obs2ioda_stage, '_build_plan', lambda run: {
        'converters': [{
            'name': 'gpsro',
            'inputs': [str(raw_obs0 if run.cycle.endswith('00:00:00Z') else raw_obs1),
                       str(runner)],
        }]
    })
    missing = startmod.check_date_inputs(root)
    assert sum(not available for _, _, available in missing) == 3
    for path in (raw_gfs, raw_obs0, raw_obs1):
        path.write_text('input')
    ready = startmod.check_date_inputs(root)
    assert all(available for _, _, available in ready)
    assert len(ready) == 4


def test_arbitrary_dates_are_explicit_not_overwritten_by_september(tmp_path):
    root = tmp_path / 'independent-period'
    create_experiment(root, start='2024-02-29T12:00:00Z')
    campaign = yaml.safe_load((root / 'campaign.yaml').read_text())
    assert campaign['calendar']['start'] == '2024-02-29T12:00:00Z'
    assert campaign['initialization'][0]['cycle'] == '2024-02-29T06:00:00Z'
    # The generated campaign may not recycle any September 2025 links.
    for link in root.joinpath('work/background').rglob('*.nc'):
        assert '2025-09' not in str(link.readlink())


def test_suggest_available_dates_requires_two_real_cycles_and_previous_gfs(tmp_path):
    from monan_jedi_workflow.experiment_start import suggest_available_dates
    input_root = tmp_path / 'inputs'
    gfs_root = tmp_path / 'gfs'
    prepnr = input_root / 'observations/prepnr/2024'
    gpsro = input_root / 'observations/gpsro/2024'
    prepnr.mkdir(parents=True)
    gpsro.mkdir(parents=True)
    gfs = gfs_root / '2024022818'
    gfs.mkdir(parents=True)
    for stamp in ('2024022900', '2024022906'):
        (prepnr / ('prepbufr.gdas.' + stamp + '.nr')).write_text('prep')
    for hour in ('00', '06'):
        (gpsro / f'gdas.gpsro.t{hour}z.20240229.bufr').write_text('gps')
    (gfs / 'gfs.t18z.pgrb2.0p25.f000').write_text('gfs')
    dates = suggest_available_dates(input_root=input_root, gfs_root=gfs_root)
    assert dates == ['2024-02-29T00:00:00Z']
    (gpsro / 'gdas.gpsro.t06z.20240229.bufr').unlink()
    assert suggest_available_dates(input_root=input_root, gfs_root=gfs_root) == []


@pytest.mark.parametrize('start,initial', [
    ('2024-02-29T00:00:00Z', '2024-02-28T18:00:00Z'),
    ('2023-01-01T00:00:00Z', '2022-12-31T18:00:00Z'),
])
def test_nonseptember_campaign_exports_all_correct_native_stage_dates(
    tmp_path, monkeypatch, start, initial
):
    from monan_jedi_workflow.domain_cli import parse_request
    from monan_jedi_workflow.platform_campaign import campaign_action
    for name in ('MONAN_JEDI_INSTALL', 'STACK', 'MONAN_INPUT', 'MONAN_MESH',
                 'MONAN_PHYSICS', 'MONAN_BMATRIX', 'MONAN_LIBFABRIC', 'MONAN_GFS'):
        monkeypatch.setenv(name + '_ROOT', str(tmp_path / name))
    root = tmp_path / 'case'
    create_experiment(root, start=start)
    result = campaign_action(
        parse_request('campaign', ['export', str(root / 'campaign.yaml')])
    )
    assert result['cycles'] == 2
    workflow = yaml.safe_load((root / 'workflow.yaml').read_text())
    assert len(workflow['initialization']['tasks']) == 9
    assert len(workflow['tasks']) == 15
    for task in workflow['initialization']['tasks']:
        assert initial in task['argv']
        assert '2025-08-31' not in str(task)
    first = workflow['tasks'][:9]
    second = workflow['tasks'][9:]
    assert all(start in task['argv'] for task in first)
    from datetime import datetime, timedelta
    following = (datetime.strptime(start, '%Y-%m-%dT%H:%M:%SZ')
                 + timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M:%SZ')
    assert all(following in task['argv'] for task in second)
