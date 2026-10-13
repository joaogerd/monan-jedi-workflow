from pathlib import Path

import pytest

from monan_jedi_workflow.case_utils import copy_clean_case
from monan_jedi_workflow.stage_config import StageConfigurationError


def test_nested_destination_excludes_campaign_storage(tmp_path: Path):
    source = tmp_path / 'template'
    source.mkdir()
    (source / 'jedi.yaml').write_text('jedi: {}\n')
    previous = source / 'cases' / 'previous'
    previous.mkdir(parents=True)
    (previous / 'stdout.log').write_text('runtime output')
    destination = source / 'cases' / 'new'
    copy_clean_case(source, destination)
    assert (destination / 'jedi.yaml').read_text() == 'jedi: {}\n'
    assert not (destination / 'cases').exists()
    assert (previous / 'stdout.log').exists()


def test_nested_destination_with_missing_parent(tmp_path: Path):
    source = tmp_path / 'template'
    source.mkdir()
    (source / 'profile.yaml').write_text('profile: {}\n')
    destination = source / 'cases' / 'new'
    copy_clean_case(source, destination)
    assert (destination / 'profile.yaml').exists()
    assert not (destination / 'cases').exists()


def test_nested_copy_still_rejects_runtime_products_in_template(tmp_path: Path):
    source = tmp_path / 'template'
    source.mkdir()
    (source / 'stdout.log').write_text('runtime output')
    with pytest.raises(StageConfigurationError, match='runtime/scientific product'):
        copy_clean_case(source, source / 'cases' / 'new')
