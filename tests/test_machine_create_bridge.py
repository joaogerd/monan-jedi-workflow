"""Opt-in bridge: machine profile may change computing paths, not DA science."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.experiment_start import create_experiment
from monan_jedi_workflow.machine_profile import (
    MachineProfileError, load_machine_profile, machine_to_legacy_site,
)
from monan_jedi_workflow.unified_cli import _experiment


def fake_runtime(tmp_path):
    workspace = tmp_path / "resources"
    workspace.mkdir()
    keys = (
        "installation_root", "stack_root", "mesh_root", "physics_root",
        "bmatrix_root", "observations_root", "gfs_root", "libfabric_root",
    )
    paths = {}
    for key in keys:
        p = workspace / key
        p.mkdir()
        paths[key] = str(p)
    install = Path(paths["installation_root"])
    stack = Path(paths["stack_root"])
    manifest = install / "share/monan-jedi/install-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "schema_version": 2,
        "ecosystem_contract_version": 2,
        "contract": "monan-jedi-runtime-v2",
        "public_anchors": ["MONAN_JEDI_INSTALL_ROOT", "STACK_ROOT"],
        "stack": {
            "env_name": "test-env", "env_module": "test-env",
            "site_setup": "site/setup.sh",
            "module_root_template": "envs/{env_name}/modules",
        },
    }))
    setup = stack / "site/setup.sh"
    setup.parent.mkdir()
    setup.write_text("#!/bin/sh\n")
    (stack / "envs/test-env/modules").mkdir(parents=True)
    return paths, setup


def machine_document(paths, setup):
    return {
        "schema_version": 1,
        "machine": {"name": "test"},
        "paths": {
            **paths,
            "work_root": str(Path(paths["installation_root"]).parent),
        },
        "execution": {"backend": "pbs",
                      "stages": {
                          "jedi": {"queue": "pesqmini", "walltime": "00:30:00",
                                   "select": 1, "ncpus": 128, "mpiprocs": 128,
                                   "launcher": "/opt/cray/pals/1.6/bin/mpiexec"},
                          "mpas": {"queue": "pesqmidi", "walltime": "01:00:00",
                                   "select": 1, "ncpus": 128, "mpiprocs": 128,
                                   "launcher": "/opt/cray/pals/1.6/bin/mpiexec"},
                          "mpas_init": {"queue": "pesqmini", "walltime": "00:30:00",
                                   "select": 1, "ncpus": 128, "mpiprocs": 128,
                                   "launcher": "/opt/cray/pals/1.6/bin/mpiexec"},
                          "wps": {"queue": "pesqmini", "walltime": "00:30:00",
                                   "select": 1, "ncpus": 1, "mpiprocs": 1,
                                   "launcher": "mpiexec"},
                          "obs2ioda": {"queue": "pesqmidi", "walltime": "01:00:00",
                                   "select": 1, "ncpus": 1, "mpiprocs": 1,
                                   "launcher": "mpiexec"},
                      }},
        "environment": {"kind": "modules", "setup": str(setup)},
    }


def test_machine_pbs_generates_equivalent_legacy_science(tmp_path):
    paths, setup = fake_runtime(tmp_path)
    profile_file = tmp_path / "machine.yaml"
    profile_file.write_text(yaml.safe_dump(machine_document(paths, setup)))
    machine = load_machine_profile(profile_file, require_existing=True)
    adapted = machine_to_legacy_site(machine)
    legacy_file = tmp_path / "site.yaml"
    legacy_file.write_text(yaml.safe_dump(adapted))

    legacy = tmp_path / "old-case"
    generated = tmp_path / "new-case"
    create_experiment(legacy, site_config=legacy_file, start="2026-01-30T00:00:00Z")
    create_experiment(
        generated, machine_profile=machine, start="2026-01-30T00:00:00Z"
    )

    def normalize_paths(value, case_root):
        """Normalize case-specific strings *after* parsing valid YAML."""
        if isinstance(value, dict):
            return {key: normalize_paths(item, case_root)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [normalize_paths(item, case_root) for item in value]
        if isinstance(value, str):
            return value.replace(str(case_root), "@CASE@")
        return value

    for relative in (
        "science/site.yaml",
        "science/jedi.yaml",
        "science/mpas.yaml",
        "science/obs2ioda.yaml",
        "science/initialization/wps.yaml",
        "science/initialization/mpas.yaml",
        "science/initialization/mpas_init.yaml",
    ):
        before = yaml.safe_load((legacy / relative).read_text())
        after = yaml.safe_load((generated / relative).read_text())
        # Compare all values and lists, ignoring only mapping order and
        # the expected experiment-root difference between independent cases.
        assert normalize_paths(before, legacy) == normalize_paths(after, generated), relative
    assert (generated / "machine-profile-lock.yaml").is_file()
    assert not (legacy / "machine-profile-lock.yaml").exists()
    assert adapted["site"]["name"] == "test"


def test_local_cannot_silently_generate_pbs_science(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    profile = tmp_path / "local.yaml"
    profile.write_text(yaml.safe_dump({
        "schema_version": 1,
        "machine": {"name": "local"},
        "paths": {"work_root": str(workspace)},
        "execution": {"backend": "local"},
        "environment": {"kind": "native"},
    }))
    case = tmp_path / "no-pbs-case"
    assert _experiment(["create", str(case), "--machine", str(profile),
                        "--start", "2026-01-30T00:00:00Z"]) == 2
    assert "require native PBS" in capsys.readouterr().err
    assert not case.exists()


def test_cli_machine_pbs_creates_case(tmp_path, capsys):
    paths, setup = fake_runtime(tmp_path)
    profile = tmp_path / "machine.yaml"
    profile.write_text(yaml.safe_dump(machine_document(paths, setup)))
    case = tmp_path / "cli-case"
    assert _experiment(["create", str(case), "--machine", str(profile),
                        "--start", "2026-01-30T00:00:00Z"]) == 0
    assert (case / "machine-profile-lock.yaml").is_file()
    assert yaml.safe_load((case / "science/site.yaml").read_text())["site"]["name"] == "test"


def test_machine_stage_resources_override_jaci_recipe_defaults(tmp_path):
    paths, setup = fake_runtime(tmp_path)
    document = machine_document(paths, setup)
    document["execution"]["stages"]["mpas"]["queue"] = "customqueue"
    document["execution"]["stages"]["mpas"]["walltime"] = "03:00:00"
    document["execution"]["stages"]["mpas"]["ncpus"] = 16
    document["execution"]["stages"]["mpas"]["mpiprocs"] = 16
    document["execution"]["stages"]["mpas"]["launcher"] = "/custom/mpi"
    document["execution"]["stages"]["wps"]["queue"] = "wq"
    document["execution"]["stages"]["obs2ioda"]["queue"] = "oq"
    document["execution"]["stages"]["jedi"]["launcher"] = "/another/mpi"
    profile = tmp_path / "machine.yaml"
    profile.write_text(yaml.safe_dump(document))
    case = tmp_path / "custom-case"
    create_experiment(case, machine_profile=load_machine_profile(profile, require_existing=True))
    for file_name in ("science/mpas.yaml", "science/initialization/mpas.yaml"):
        pbs = yaml.safe_load((case / file_name).read_text())["mpas"]["pbs"]
        assert (pbs["queue"], pbs["walltime"], pbs["ncpus"], pbs["mpiprocs"]) == (
            "customqueue", "03:00:00", 16, 16)
        assert pbs["launcher"] == "/custom/mpi"
    assert yaml.safe_load((case / "science/jedi.yaml").read_text())["jedi"]["pbs"]["launcher"] == "/another/mpi"
    assert yaml.safe_load((case / "science/initialization/wps.yaml").read_text())["wps"]["pbs"]["queue"] == "wq"
    assert yaml.safe_load((case / "science/obs2ioda.yaml").read_text())["obs2ioda"]["pbs"]["queue"] == "oq"


def test_missing_stage_policy_fails_before_creating_case(tmp_path):
    paths, setup = fake_runtime(tmp_path)
    document = machine_document(paths, setup)
    del document["execution"]["stages"]["wps"]
    profile_file = tmp_path / "machine.yaml"
    profile_file.write_text(yaml.safe_dump(document))
    machine = load_machine_profile(profile_file, require_existing=True)
    case = tmp_path / "missing-stage"
    with pytest.raises(MachineProfileError, match="wps"):
        create_experiment(case, machine_profile=machine)
    assert not case.exists()


def test_missing_runtime_aborts_before_case_creation(tmp_path):
    paths, setup = fake_runtime(tmp_path)
    document = machine_document(paths, setup)
    document["environment"]["setup"] = str(tmp_path / "wrong-setup.sh")
    profile_file = tmp_path / "machine.yaml"
    profile_file.write_text(yaml.safe_dump(document))
    # Failed path validation precedes any case output.
    case = tmp_path / "no-case"
    with pytest.raises(MachineProfileError, match="does not exist"):
        machine = load_machine_profile(profile_file, require_existing=True)
        create_experiment(case, machine_profile=machine)
    assert not case.exists()
