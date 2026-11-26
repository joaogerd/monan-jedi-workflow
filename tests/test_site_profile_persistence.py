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



def test_missing_workspace_profile_and_ambiguous_stack_fails_early(tmp_path, monkeypatch):
    import monan_jedi_workflow.experiment_environment as environment
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(environment, "_workspace", lambda root: workspace)
    monkeypatch.setattr(environment, "_discover_stack", lambda root: None)
    monkeypatch.delenv("STACK_ROOT", raising=False)
    case = workspace / "work" / "not-created"
    with pytest.raises(ValueError, match="experiment site init"):
        create_experiment(case, start="2026-01-29T00:00:00Z")
    assert not case.exists()



def test_first_use_discovers_unique_stack_and_creates_site_automatically(
    tmp_path, monkeypatch
):
    import monan_jedi_workflow.experiment_environment as environment
    workspace, paths = _fixture(tmp_path)
    # Arrange the one actual stack installation in the documented scan path.
    original = Path(paths["STACK_ROOT"])
    discovered = workspace / "work" / "spack-stack-production" / "spack-stack"
    discovered.parent.mkdir(parents=True)
    original.rename(discovered)
    paths["STACK_ROOT"] = str(discovered)
    monkeypatch.setattr(environment, "_workspace", lambda root: workspace)
    monkeypatch.setattr(
        environment, "_defaults",
        lambda root: {k: Path(v) for k, v in paths.items() if k != "STACK_ROOT"},
    )
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)
    root = workspace / "work" / "first-ever-case"
    assert not (workspace / "site.yaml").exists()
    create_experiment(root, start="2026-01-30T00:00:00Z")
    persisted = yaml.safe_load((workspace / "site.yaml").read_text())
    assert persisted["stack"]["root"] == str(discovered)
    assert yaml.safe_load((root / "science/site.yaml").read_text())["stack"]["root"] == str(discovered)
    check = subprocess.run(
        ["bash", "-c", 'source "$1"; test "$STACK_ROOT" = "$2"',
         "bash", str(root / "environment.sh"), str(discovered)],
        env={"PATH": os.environ["PATH"]}, capture_output=True, text=True,
    )
    assert check.returncode == 0, check.stderr


def test_ambiguous_stacks_print_choices_and_explicit_select_works(
    tmp_path, monkeypatch
):
    import monan_jedi_workflow.experiment_environment as environment
    workspace, paths = _fixture(tmp_path)
    monkeypatch.setattr(environment, "_workspace", lambda root: workspace)
    monkeypatch.setattr(
        environment, "_defaults",
        lambda root: {k: Path(v) for k, v in paths.items() if k != "STACK_ROOT"},
    )
    stacks = []
    for name in ("spack-stack-production", "spack-stack-testing"):
        stack = workspace / "work" / name / "spack-stack"
        setup = stack / "configs/sites/tier2/jaci/setup.sh"
        setup.parent.mkdir(parents=True)
        setup.write_text("# valid\n")
        (stack / "envs/test/modules").mkdir(parents=True)
        stacks.append(stack)
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)
    case = workspace / "work" / "new"
    with pytest.raises(ValueError, match="2 valid candidates") as exc:
        create_experiment(case)
    assert str(stacks[0]) in str(exc.value)
    assert str(stacks[1]) in str(exc.value)
    assert not case.exists()
    assert not (workspace / "site.yaml").exists()
    initialized = environment.initialize_site(case, stack=stacks[0])
    assert initialized == workspace / "site.yaml"
    create_experiment(case, start="2026-01-30T00:00:00Z")
    assert (case / "environment.sh").exists()



def test_first_time_interactive_setup_asks_stack_and_creates_profile(
    tmp_path, monkeypatch
):
    import monan_jedi_workflow.experiment_environment as environment
    workspace, paths = _fixture(tmp_path)
    monkeypatch.setattr(environment, "_workspace", lambda root: workspace)
    monkeypatch.setattr(
        environment, "_defaults",
        lambda root: {k: Path(v) for k, v in paths.items() if k != "STACK_ROOT"},
    )
    stacks = []
    for name in ("spack-stack-A", "spack-stack-B"):
        stack = workspace / "work" / name / "spack-stack"
        setup = stack / "configs/sites/tier2/jaci/setup.sh"
        setup.parent.mkdir(parents=True)
        setup.write_text("# setup\n")
        (stack / "envs/test/modules").mkdir(parents=True)
        stacks.append(stack)
    answers = iter(["2"])
    profile = environment.initialize_site(
        workspace / "work" / "first-experiment",
        environ={},
        interactive=True,
        input_fn=lambda prompt: next(answers),
    )
    assert profile.is_file()
    assert yaml.safe_load(profile.read_text())["stack"]["root"] == str(stacks[1])


def test_first_time_interactive_setup_requests_missing_scientific_root(
    tmp_path, monkeypatch
):
    import monan_jedi_workflow.experiment_environment as environment
    workspace, paths = _fixture(tmp_path)
    monkeypatch.setattr(environment, "_workspace", lambda root: workspace)
    monkeypatch.setattr(
        environment, "_defaults",
        lambda root: {k: Path(v) for k, v in paths.items()},
    )
    missing = Path(paths["MONAN_GFS_ROOT"])
    missing.rmdir()
    correct = workspace / "real-gfs"
    correct.mkdir()
    path = environment.initialize_site(
        workspace / "work" / "experiment",
        environ={},
        stack=Path(paths["STACK_ROOT"]),
        interactive=True,
        input_fn=lambda prompt: str(correct)
           if prompt.startswith("MONAN_GFS_ROOT") else "",
    )
    assert yaml.safe_load(path.read_text())["environment"]["MONAN_GFS_ROOT"] == str(correct)



def test_isolated_workspace_bootstrap_does_not_consume_or_modify_primary_site(
    tmp_path, monkeypatch
):
    import monan_jedi_workflow.experiment_environment as environment
    real_workspace, paths = _fixture(tmp_path)
    isolated = real_workspace / "onboarding-test"
    isolated.mkdir()
    # The real JACI project may already have a successfully configured site.
    existing = real_workspace / "site.yaml"
    existing.write_text("DO_NOT_TOUCH: true\n")
    monkeypatch.setattr(environment, "_workspace", lambda root: real_workspace)
    monkeypatch.setattr(
        environment, "_defaults",
        lambda root: {k: Path(v) for k, v in paths.items() if k != "STACK_ROOT"},
    )
    selected = real_workspace / "work" / "spack-stack-inpe-overlay" / "spack-stack"
    source = Path(paths["STACK_ROOT"])
    selected.parent.mkdir(parents=True)
    source.rename(selected)
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)
    case = isolated / "experiments" / "first-ever"
    create_experiment(
        case, start="2026-01-30T00:00:00Z", workspace=isolated,
    )
    assert existing.read_text() == "DO_NOT_TOUCH: true\n"
    assert (isolated / "site.yaml").is_file()
    assert yaml.safe_load((isolated / "site.yaml").read_text())["stack"]["root"] == str(selected)
    assert (case / "environment.sh").is_file()
    assert (case / "science/site.yaml").is_file()


def test_isolated_workspace_rejects_nonexistent_and_outside_project(
    tmp_path, monkeypatch
):
    import monan_jedi_workflow.experiment_environment as environment
    real_workspace, paths = _fixture(tmp_path)
    monkeypatch.setattr(environment, "_workspace", lambda root: real_workspace)
    case = real_workspace / "case"
    with pytest.raises(ValueError, match="does not exist"):
        create_experiment(case, workspace=real_workspace / "not-created")
    assert not case.exists()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ValueError, match="must be inside"):
        create_experiment(case, workspace=outside)
    assert not case.exists()



def test_portable_non_jaci_case_without_site_profile(tmp_path, monkeypatch):
    """A missing JACI workspace must not block ordinary case generation."""
    from monan_jedi_workflow import experiment_environment as environment
    monkeypatch.setattr(environment, "_workspace", lambda root: None)
    root = tmp_path / "portable-case"
    create_experiment(root, start="2024-02-29T00:00:00Z")
    assert (root / "environment.sh").is_file()
    assert (root / "science/site.yaml").is_file()
    assert (root / "campaign.yaml").is_file()
    assert not (tmp_path / "site.yaml").exists()


def test_explicit_site_bypasses_implicit_workspace_resolution(tmp_path, monkeypatch):
    """--site must not depend on /p/projetos or create a shared profile."""
    from monan_jedi_workflow import experiment_environment as environment
    workspace, paths = _fixture(tmp_path)
    site = workspace / "explicit.yaml"
    site.write_text(yaml.safe_dump({
        "site": {"name": "jaci"},
        "stack": {"load": True, "root": paths["STACK_ROOT"]},
        "jedi": {"install_root": paths["MONAN_JEDI_INSTALL_ROOT"]},
        "environment": {
            name: value for name, value in paths.items()
            if name not in ("STACK_ROOT", "MONAN_JEDI_INSTALL_ROOT")
        },
    }))
    monkeypatch.setattr(environment, "_workspace", lambda root: None)
    case = tmp_path / "explicit-site-case"
    create_experiment(case, site_config=site)
    assert yaml.safe_load((case / "science/site.yaml").read_text())["stack"]["root"] == paths["STACK_ROOT"]
    assert not (tmp_path / "site.yaml").exists()


def test_explicit_machine_environment_does_not_probe_jaci_defaults(tmp_path, monkeypatch):
    """A declared machine runtime must not depend on JACI autodiscovery."""
    from monan_jedi_workflow import experiment_environment as environment

    def unexpected_discovery(*args, **kwargs):
        raise AssertionError("JACI-specific discovery must be disabled for machine.yaml")

    monkeypatch.setattr(environment, "_workspace", unexpected_discovery)
    monkeypatch.setattr(environment, "_defaults", unexpected_discovery)
    profile = {
        "stack": {"root": "/declared/stack"},
        "jedi": {"install_root": "/declared/install"},
        "environment": {
            "MONAN_MESH_ROOT": "/declared/mesh",
            "MONAN_PHYSICS_ROOT": "/declared/physics",
            "MONAN_BMATRIX_ROOT": "/declared/bmatrix",
            "MONAN_INPUT_ROOT": "/declared/input",
            "MONAN_GFS_ROOT": "/declared/gfs",
            "MONAN_LIBFABRIC_ROOT": "/declared/libfabric",
        },
    }
    result = environment.render_environment(
        tmp_path / "case",
        environ={},
        site_profile=profile,
        allow_legacy_discovery=False,
    )
    assert "export STACK_ROOT=/declared/stack" in result
    assert "export MONAN_JEDI_INSTALL_ROOT=/declared/install" in result
    assert "/p/projetos" not in result
    assert "MONAN_JACI_LOADER optional" in result
