"""Public grammar must reject ambiguous operations before dispatch."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import pytest

T = '2025-09-01T00:00:00Z'
VERBS = ('inspect', 'check', 'prepare', 'run', 'validate', 'status')

def parse(app, args):
    from monan_jedi_workflow.domain_cli import parse_request
    return parse_request(app, args)

@pytest.mark.parametrize('app,operation,prefix', [
    ('jedi', 'assimilation', []), ('mpas', 'forecast', []),
    ('diagnostics', 'diagnostics', []), ('obs', 'acquire', ['acquire']),
    ('obs', 'convert', ['convert']), ('mpas', 'init', ['init']),
])
@pytest.mark.parametrize('verb', VERBS)
def test_domain_verbs(app, operation, prefix, verb):
    r = parse(app, [*prefix, verb, 'missing.yaml', '--cycle', T, '--json'])
    assert (r.app, r.operation, r.action, r.config, r.cycle, r.json_output) == (
        app, operation, verb, Path('missing.yaml'), T, True)
    with pytest.raises(FrozenInstanceError):
        r.action = 'other'

@pytest.mark.parametrize('verb', ['inspect', 'check', 'export'])
def test_campaign(verb):
    r = parse('campaign', [verb, 'campaign.yaml'])
    assert r.cycle is None
    assert r.action == verb
    assert r.engine == ('simpleworkflow' if verb == 'export' else None)

@pytest.mark.parametrize('app,args', [
    ('jedi', ['run', 'x.yaml']), ('obs', ['run', 'x.yaml', '--cycle', T]),
    ('campaign', ['run', 'x.yaml']),
    ('jedi', ['run', 'x.yaml', '--cycle', T, '--start', T]),
    ('mpas', ['run', 'x.yaml', '--cycle', T, '--end', T]),
    ('jedi', ['run', 'x.yaml', '--cycle', T, '--source', 'gpsro']),
    ('jedi', ['run', 'x.yaml', '--cycle', T, '--engine', 'ecflow']),
    ('campaign', ['inspect', 'x.yaml', '--engine', 'ecflow']),
    ('jedi', ['ru', 'x.yaml', '--cycle', T]),
    ('jedi', ['run', 'x.yaml', '--cycl', T]),
])
def test_invalid_grammar(app, args):
    with pytest.raises(SystemExit) as e:
        parse(app, args)
    assert e.value.code == 2

@pytest.mark.parametrize('cycle', ['2025-09-01', '2025-09-01T00:00:00',
    '2025-09-01T00:00:00+03:00', '2025-02-30T00:00:00Z', 'nonsense'])
def test_invalid_cycle(cycle):
    with pytest.raises(SystemExit) as e:
        parse('jedi', ['run', 'x.yaml', '--cycle', cycle])
    assert e.value.code == 2

def test_selectors():
    r = parse('obs', ['convert', 'run', 'x.yaml', '--cycle', T, '--source', 'gpsro'])
    assert r.source == 'gpsro'
    assert parse('campaign', ['export', 'x.yaml', '--engine', 'ecflow']).engine == 'ecflow'


def test_utc_offset():
    assert parse('jedi', ['run', 'x.yaml', '--cycle', '2025-09-01T00:00:00+00:00']).cycle.endswith('+00:00')


def test_parser_does_not_read_files_or_import_backends(tmp_path):
    import subprocess
    import sys
    script = '''
import builtins, sys
from monan_jedi_workflow.domain_cli import parse_request

def reject(*args, **kwargs):
    raise AssertionError('parser must not read files')
builtins.open = reject
from pathlib import Path
Path.open = reject
for app, prefix in [('jedi', []), ('mpas', []), ('diagnostics', []),
                    ('obs', ['acquire']), ('obs', ['convert']), ('mpas', ['init'])]:
    for verb in ('inspect', 'check', 'prepare', 'run', 'validate', 'status'):
        parse_request(app, prefix + [verb, '/missing/experiment.yaml', '--cycle', '2025-09-01T00:00:00Z'])
for verb in ('inspect', 'check', 'export'):
    parse_request('campaign', [verb, '/missing/campaign.yaml'])
assert not any(name in sys.modules for name in (
    'monan_jedi_workflow.cli_frontend', 'monan_jedi_workflow.campaign',
    'monan_jedi_workflow.jedi_stage', 'monan_jedi_workflow.mpas_stage',
    'monan_jedi_workflow.obs_acquisition', 'monan_jedi_workflow.scheduler'))
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_mpas_help_lists_init(capsys):
    with pytest.raises(SystemExit) as e:
        parse('mpas', ['--help'])
    assert e.value.code == 0
    assert 'init' in capsys.readouterr().out
