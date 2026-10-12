import importlib.util
import json
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/capture_m3_reference.py'


def module():
    spec = importlib.util.spec_from_file_location('capture_m3_reference', SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_capture_keeps_geometry_and_link_targets_without_scientific_data(tmp_path):
    reference = tmp_path / 'CASE'
    case = reference / 'cases/jedi-2018041500-fgat-corrected'
    case.mkdir(parents=True)
    support = tmp_path / 'support'
    support.mkdir()
    (support / 'geovars.yaml').write_text('variables: [temperature]\n')
    (case / 'jedi.yaml').write_text('jedi:\n  variables: {}\n')
    geometry = case / 'geometry/2018041500'
    geometry.mkdir(parents=True)
    (geometry / 'streams.atmosphere.outer').write_text('<streams/>\n')
    (geometry / 'geovars.yaml').symlink_to(support / 'geovars.yaml')
    (geometry / 'loop').symlink_to(case, target_is_directory=True)
    (case / 'Data').mkdir()
    (case / 'Data/scientific.nc').write_bytes(b'large scientific data')
    (case / 'jedi.stdout.log').write_text('runtime log excluded')
    output = tmp_path / 'capture'
    manifest, archive = module().capture(reference, output)
    record = json.loads(manifest.read_text())
    assert any(item['source'].endswith('streams.atmosphere.outer') for item in record['files'])
    assert any(item['resolved'] == str(support / 'geovars.yaml') for item in record['files'])
    with tarfile.open(archive) as bundle:
        assert not any(name.endswith('.nc') or name.endswith('.log') for name in bundle.getnames())
        assert any(name.endswith('geovars.yaml') for name in bundle.getnames())
    assert (case / 'jedi.stdout.log').read_text() == 'runtime log excluded'


def test_capture_refuses_to_replace_previous_capture(tmp_path):
    reference = tmp_path / 'CASE'
    reference.mkdir()
    output = tmp_path / 'capture'
    output.mkdir()
    with pytest.raises(FileExistsError):
        module().capture(reference, output)
