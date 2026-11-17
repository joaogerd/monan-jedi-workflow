"""Persistent site.yaml is the authority for new terminal and native PBS roots."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

from monan_jedi_workflow.experiment_environment import (
    REQUIRED,
    load_project_site,
    render_environment,
    save_project_site,
)
from monan_jedi_workflow.experiment_start import create_experiment


def _fixture(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    paths = {}
    for key in REQUIRED:
        value = workspace / key.lower()
        value.mkdir(parents=True)
        paths[key] = str(value)
    install = Path(paths["MONAN_JEDI_INSTALL_ROOT"])
    stack = Path(paths["STACK_ROOT"])
    manifest = install / "share/monan-jedi/install-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "schema_version": 2,
        "ecosystem_contract_version": 2,
        "contract": "monan-jedi-runtime-v2",
        "public_anchors": ["MONAN_JEDI_INSTALL_ROOT", "STACK_ROOT"],
        "stack": {
            "env_name": "test",
            "env_module": "test/test-env",
            "site_setup": "configs/sites/tier2/jaci/setup.sh",
            "module_root_template": "envs/{env_name}/modules",
        },
    }))
    (stack / "configs/sites/tier2/jaci").mkdir(parents=True)
    (stack / "configs/sites/tier2/jaci/setup.sh").write_text("# valid setup\n")
    (stack / "envs/test/modules").mkdir(parents=True)
    return workspace, paths


def test_save_site_and_create_new_experiment_without_inherited_stack(tmp_path, monkeypatch):
    import monan_jedi_workflow.experiment_environment as environment
    workspace, paths = _fixture(tmp_path)
    monkeypatch.setattr(environment, "_workspace", lambda root: workspace)
    saved = save_project_site(workspace / "work", environ=paths)
    assert saved == workspace / "site.yaml"
    assert saved.exists()
    with pytest.raises(FileExistsError, match="overwrite"):
        save_project_site(workspace / "work", environ=paths)

    # A new shell does not inherit any MONAN_* or STACK_ROOT from the
    # successful previous experiment. The saved site is sufficient.
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)
    root = workspace / "work" / "fresh-2026"
    create_experiment(root, start="2026-01-29T00:00:00Z")
    generated_site = yaml.safe_load((root / "science/site.yaml").read_text())
    assert generated_site["stack"]["root"] == paths["STACK_ROOT"]
    assert generated_site["jedi"]["install_root"] == paths["MONAN_JEDI_INSTALL_ROOT"]
    assert generated_site["runtime"]["validate_python"] is False
    script = root / "environment.sh"
    assert f"export STACK_ROOT={paths['STACK_ROOT']}" in script.read_text()
    assert f"export MONAN_JEDI_INSTALL_ROOT={paths['MONAN_JEDI_INSTALL_ROOT']}" in script.read_text()

    result = subprocess.run(
        ["bash", "-c", 'source "$1" && test "$STACK_ROOT" = "$2" && '
                      'test "$MONAN_JEDI_INSTALL_ROOT" = "$3"',
         "bash", str(script), paths["STACK_ROOT"], paths["MONAN_JEDI_INSTALL_ROOT"]],
        env={"PATH": os.environ["PATH"]}, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "[OK]" in result.stdout


def test_explicit_site_file_works_outside_workspace(tmp_path):
    workspace, paths = _fixture(tmp_path)
    site = workspace / "site.yaml"
    site.write_text(yaml.safe_dump({
        "site": {"name": "jaci"},
        "stack": {"load": True, "root": paths["STACK_ROOT"]},
        "jedi": {"install_root": paths["MONAN_JEDI_INSTALL_ROOT"]},
        "environment": {key: value for key, value in paths.items()
                        if key not in {"STACK_ROOT", "MONAN_JEDI_INSTALL_ROOT"}},
    }))
    root = tmp_path / "elsewhere" / "case"
    create_experiment(root, start="2024-02-29T00:00:00Z", site_config=site)
    assert yaml.safe_load((root / "science/site.yaml").read_text())["stack"]["root"] == paths["STACK_ROOT"]


def test_unresolved_shared_site_anchor_fails_before_creating_case(tmp_path, monkeypatch):
    workspace, paths = _fixture(tmp_path)
    profile = workspace / "site.yaml"
    profile.write_text(
        "site:\n  name: jaci\nstack:\n  load: true\n  root: ${STACK_ROOT}\n"
        + f"jedi:\n  install_root: {paths['MONAN_JEDI_INSTALL_ROOT']}\n"
    )
    monkeypatch.delenv("STACK_ROOT", raising=False)
    root = tmp_path / "case"
    with pytest.raises(ValueError, match="unresolved environment"):
        create_experiment(root, site_config=profile)
    assert not root.exists()
