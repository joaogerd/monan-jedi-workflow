"""Machine profile contract tests: no JACI filesystem, Spack, PBS or science required."""
from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.machine_profile import (
    MachineProfileError,
    load_machine_profile,
)


def write_profile(tmp_path, **updates):
    document = {
        "schema_version": 1,
        "machine": {"name": "local"},
        "paths": {"work_root": str(tmp_path / "workspace")},
        "execution": {"backend": "local", "max_cores": 4},
        "environment": {"kind": "native"},
    }
    document.update(updates)
    path = tmp_path / "machine.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_local_profile_without_jaci_spack_or_scientific_install(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    profile = load_machine_profile(write_profile(tmp_path), require_existing=True)
    assert profile.name == "local"
    assert profile.backend == "local"
    assert profile.paths["work_root"] == workspace.resolve()
    assert profile.describe()["execution"]["max_cores"] == 4


def test_pbs_profile_is_configuration_not_submission(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    setup = tmp_path / "setup.sh"
    setup.write_text("#!/bin/sh\n", encoding="utf-8")
    path = write_profile(
        tmp_path, machine={"name": "jaci"},
        paths={"work_root": str(root), "stack_root": str(root)},
        execution={"backend": "pbs", "queue": "pesqmidi",
                   "walltime": "01:00:00"},
        environment={"kind": "modules", "setup": str(setup)},
    )
    resolved = load_machine_profile(path, require_existing=True)
    assert resolved.backend == "pbs"
    assert resolved.environment["setup"] == str(setup)
    assert not (root / "science").exists()


def test_explicit_env_expansion(tmp_path):
    path = write_profile(
        tmp_path, paths={"work_root": "${MY_TEST_WORKSPACE}"}
    )
    profile = load_machine_profile(
        path, environ={"MY_TEST_WORKSPACE": str(tmp_path)}
    )
    assert profile.paths["work_root"] == tmp_path.resolve()


def test_undefined_environment_variable_is_rejected(tmp_path):
    path = write_profile(
        tmp_path, paths={"work_root": "${UNKNOWN_MACHINE_PROFILE_ROOT}"}
    )
    with pytest.raises(MachineProfileError, match="undefined environment variable"):
        load_machine_profile(path, environ={})


@pytest.mark.parametrize("changes, diagnostic", [
    ({"schema_version": 2}, "schema_version"),
    ({"machine": {"name": "../jaci"}}, "machine.name"),
    ({"execution": {"backend": "unknown"}}, "execution.backend"),
    ({"execution": {"backend": "local", "queue": "short"}}, "cannot define"),
    ({"execution": {"backend": "local", "max_cores": 0}}, "max_cores"),
    ({"environment": {"kind": "invalid"}}, "environment.kind"),
    ({"environment": {"kind": "modules"}}, "environment.setup"),
    ({"paths": {"gfs_root": "/tmp"}}, "work_root"),
    ({"paths": {"work_root": "relative/work"}}, "absolute path"),
    ({"paths": {"work_root": "/tmp", "science_method": "3dvar"}}, "Unsupported path"),
])
def test_invalid_profiles_fail_with_actionable_errors(tmp_path, changes, diagnostic):
    path = write_profile(tmp_path, **changes)
    with pytest.raises(MachineProfileError, match=diagnostic):
        load_machine_profile(path)


def test_profile_validation_never_creates_directories(tmp_path):
    missing = tmp_path / "not-created"
    path = write_profile(tmp_path, paths={"work_root": str(missing)})
    with pytest.raises(MachineProfileError, match="does not exist"):
        load_machine_profile(path, require_existing=True)
    assert not missing.exists()


def test_existing_v0_jaci_site_profile_not_misrepresented_as_v1(tmp_path):
    path = tmp_path / "site.yaml"
    path.write_text("site:\n  name: jaci\nstack:\n  load: true\n")
    with pytest.raises(MachineProfileError, match="schema_version"):
        load_machine_profile(path)


def test_cli_machine_validate_and_show_without_scheduler(tmp_path, capsys):
    from monan_jedi_workflow.unified_cli import _experiment
    (tmp_path / "workspace").mkdir()
    filename = write_profile(tmp_path)
    assert _experiment(["machine", "validate", str(filename), "--check-paths"]) == 0
    assert "[OK]" in capsys.readouterr().out
    assert _experiment(["machine", "show", str(filename)]) == 0
    normalized = yaml.safe_load(capsys.readouterr().out)
    assert normalized["machine"]["name"] == "local"
    assert normalized["execution"]["backend"] == "local"


def test_cli_machine_rejects_bad_profile(tmp_path, capsys):
    from monan_jedi_workflow.unified_cli import _experiment
    filename = write_profile(tmp_path, execution={"backend": "invalid"})
    assert _experiment(["machine", "validate", str(filename)]) == 2
    assert "execution.backend" in capsys.readouterr().err
