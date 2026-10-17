"""Beta integration tests execute actual local workers, never PBS mocks."""

import json
import sys
from pathlib import Path
import pytest
import yaml

T = "2025-09-01T00:00:00Z"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value))
    return path


def case(tmp_path):
    source = tmp_path / "science"
    source.mkdir()
    driver = source / "forecast.py"
    driver.write_text(
        "from pathlib import Path\nPath('state.nc').write_text('state')\nprint('COMPLETE')\n"
    )
    write(
        source / "forecast.yaml",
        {
            "mpas": {
                "run_dir": "forecast/{cycle_id}",
                "lead_hours": 6,
                "pbs": {
                    "queue": "test",
                    "walltime": "00:01:00",
                    "mpiprocs": 1,
                    "command": [sys.executable, str(driver)],
                },
                "validation": {
                    "log": "stdout.log",
                    "required_log_markers": ["COMPLETE"],
                    "required_outputs": ["state.nc"],
                },
            }
        },
    )
    return write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "test", "destination": "./results"},
            "site": {"execution": {"mode": "local"}},
            "mpas": "./science/forecast.yaml",
        },
    )


def call(app, action, config, *extra):
    from monan_jedi_workflow.platform_cli import main

    return main(app, [action, str(config), "--cycle", T, "--json", *extra])


def test_inspect_and_check_are_read_only(tmp_path, capsys):
    config = case(tmp_path)
    assert call("mpas", "inspect", config) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["app"] == "mpas"
    assert call("mpas", "check", config) == 0
    assert not (tmp_path / "results").exists()


def test_native_worker_prepare_run_validate(tmp_path, capsys):
    config = case(tmp_path)
    for action in ["prepare", "run", "validate", "status"]:
        assert call("mpas", action, config) == 0, capsys.readouterr().out
    state = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert state["state"] == "validated"
    assert (tmp_path / "results/forecast/20250901T000000Z/state.nc").is_file()


def test_run_requires_prepare(tmp_path, capsys):
    assert call("mpas", "run", case(tmp_path)) != 0
    assert not (tmp_path / "results").exists()


def test_configuration_change_refuses_reuse(tmp_path, capsys):
    config = case(tmp_path)
    assert call("mpas", "prepare", config) == 0
    data = yaml.safe_load((tmp_path / "science/forecast.yaml").read_text())
    data["mpas"]["lead_hours"] = 12
    write(tmp_path / "science/forecast.yaml", data)
    assert call("mpas", "run", config) != 0
    assert "changed" in capsys.readouterr().out.lower()


def test_domain_subset_does_not_load_jedi(tmp_path, capsys):
    config = case(tmp_path)
    data = yaml.safe_load(config.read_text())
    data["jedi"] = "missing.yaml"
    write(config, data)
    assert call("mpas", "check", config) == 0


def test_pbs_worker_cannot_run_on_login(tmp_path, monkeypatch, capsys):
    config = case(tmp_path)
    data = yaml.safe_load(config.read_text())
    data["site"] = {"execution": {"mode": "pbs"}}
    write(config, data)
    monkeypatch.delenv("PBS_JOBID", raising=False)
    assert call("mpas", "prepare", config) == 0
    assert call("mpas", "run", config) != 0
    assert "PBS" in capsys.readouterr().out


def test_source_file_paths_are_relative_to_declaring_file(tmp_path, capsys):
    config = case(tmp_path)
    data = yaml.safe_load((tmp_path / "science/forecast.yaml").read_text())
    data["mpas"]["templates"] = [
        {"source": "namelist.in", "target": "namelist.atmosphere"}
    ]
    (tmp_path / "science/namelist.in").write_text("time={mpas_time}")
    write(tmp_path / "science/forecast.yaml", data)
    assert call("mpas", "prepare", config) == 0
    assert (
        tmp_path / "results/forecast/20250901T000000Z/namelist.atmosphere"
    ).is_file()


def test_acquire_one_cycle_and_convert(tmp_path, capsys):
    raw = tmp_path / "raw.bufr"
    raw.write_bytes(b"raw")
    conversion = tmp_path / "convert.py"
    conversion.write_text(
        "from pathlib import Path\nPath('obs.h5').write_bytes(b'IODA')\n"
    )
    obs = write(
        tmp_path / "obs.yaml",
        {
            "acquisition": {
                "sources": [
                    {
                        "name": "sondes",
                        "source": str(raw),
                        "destination": "raw/{cycle_id}/obs.bufr",
                    }
                ]
            },
            "obs2ioda": {
                "work_dir": "obs/{cycle_id}",
                "inspection": {"argv": [sys.executable, "-c", "print('IODA')"]},
                "converters": [
                    {
                        "name": "sondes",
                        "inputs": [str(raw)],
                        "argv": [sys.executable, str(conversion)],
                        "outputs": ["{work_dir}/obs.h5"],
                        "validation": {"required_header_markers": ["IODA"]},
                    }
                ],
            },
        },
    )
    config = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "obs", "destination": "./results"},
            "observations": str(obs),
        },
    )
    from monan_jedi_workflow.platform_cli import main

    for operation in ["acquire", "convert"]:
        for action in ["inspect", "check", "prepare", "run", "validate", "status"]:
            assert (
                main("obs", [operation, action, str(config), "--cycle", T, "--json"])
                == 0
            ), capsys.readouterr().out
    assert (tmp_path / "results/raw/20250901T000000Z/obs.bufr").read_bytes() == b"raw"


def test_diagnostics_cost_function(tmp_path, capsys):
    log = tmp_path / "jedi.log"
    log.write_text("iteration 0 J = 100\niteration 1 J = 65\n")
    config = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "diag", "destination": "./results"},
            "diagnostics": {
                "run_dir": "diagnostics/{cycle_id}",
                "cost_function": {"log": str(log)},
            },
        },
    )
    for action in ["prepare", "run", "validate"]:
        assert call("diagnostics", action, config) == 0, capsys.readouterr().out
    data = json.loads(
        (tmp_path / "results/diagnostics/20250901T000000Z/summary.json").read_text()
    )
    assert data["cost_function"]["reduction_percent"] == 35.0


def test_export_is_pure_and_inclusive(tmp_path, capsys):
    config = case(tmp_path)
    campaign = write(
        tmp_path / "campaign.yaml",
        {
            "schema_version": 1,
            "experiment": str(config),
            "calendar": {"start": T, "end": "2025-09-08T00:00:00Z", "interval": "PT6H"},
            "operations": ["mpas"],
            "last_cycle": {"forecast": False},
            "output": "./workflow.yaml",
        },
    )
    from monan_jedi_workflow.platform_cli import main

    assert main("campaign", ["inspect", str(campaign), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["cycles"] == 29
    assert not (tmp_path / "workflow.yaml").exists()
    assert main("campaign", ["export", str(campaign), "--json"]) == 0
    workflow = yaml.safe_load((tmp_path / "workflow.yaml").read_text())
    assert len(workflow["tasks"]) == 84
    assert all("qsub" not in str(t) for t in workflow["tasks"])
    assert not (tmp_path / "results").exists()


def test_jedi_worker_and_initialization(tmp_path, capsys):
    source = tmp_path / "science"
    source.mkdir()
    background = source / "background.nc"
    background.write_text("state")
    skeleton = source / "skeleton"
    skeleton.mkdir()
    (skeleton / "fixed.tbl").write_text("fixed")
    driver = source / "analysis.py"
    driver.write_text(
        "from pathlib import Path\nPath('analysis.nc').write_text('analysis')\nprint('OOPS Ending')\n"
    )
    shared = {
        "run_dir": "jedi/{cycle_id}",
        "runtime": {"skeleton": "skeleton"},
        "background": {"source": "background.nc", "target": "background.nc"},
        "pbs": {
            "queue": "test",
            "walltime": "00:01:00",
            "mpiprocs": 1,
            "command": [sys.executable, str(driver)],
        },
        "validation": {
            "log": "jedi.stdout.log",
            "required_log_markers": ["OOPS Ending"],
            "required_outputs": ["analysis.nc"],
        },
    }
    write(source / "jedi.yaml", {"jedi": shared})
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "analysis", "destination": "results"},
            "site": {"execution": {"mode": "local"}},
            "jedi": "science/jedi.yaml",
        },
    )
    for action in ["check", "prepare", "run", "validate"]:
        assert call("jedi", action, cfg) == 0, capsys.readouterr().out
    assert (tmp_path / "results/jedi/20250901T000000Z/fixed.tbl").is_file()


def test_native_detects_modified_executable_input(tmp_path, capsys):
    config = case(tmp_path)
    assert call("mpas", "prepare", config) == 0
    (tmp_path / "science/forecast.py").write_text("raise RuntimeError('modified')")
    assert call("mpas", "run", config) != 0
    assert "changed" in capsys.readouterr().out.lower()


def test_conversion_relative_input(tmp_path, capsys):
    raw = tmp_path / "raw.bufr"
    raw.write_text("raw")
    write(
        tmp_path / "obs.yaml",
        {
            "obs2ioda": {
                "work_dir": "obs/{cycle_id}",
                "inspection": {"argv": ["echo", "IODA"]},
                "converters": [
                    {
                        "name": "sondes",
                        "inputs": ["raw.bufr"],
                        "outputs": ["{work_dir}/obs.h5"],
                        "argv": ["echo", "convert"],
                    }
                ],
            }
        },
    )
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "obs", "destination": "results"},
            "observations": "obs.yaml",
        },
    )
    from monan_jedi_workflow.platform_cli import main

    assert (
        main("obs", ["convert", "check", str(cfg), "--cycle", T, "--json"]) == 0
    ), capsys.readouterr().out


def test_departures_statistics(tmp_path, capsys):
    import numpy as np
    from netCDF4 import Dataset

    path = tmp_path / "diag.nc"
    with Dataset(path, "w") as ds:
        ds.createDimension("Location", 2)
        for name, values in [("ombg", [2.0, 4.0]), ("oman", [1.0, 2.0])]:
            var = ds.createGroup(name).createVariable(
                "airTemperature", "f8", ("Location",)
            )
            var.units = "K"
            var[:] = values
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "diag", "destination": "results"},
            "diagnostics": {"departures": {"files": [str(path)]}},
        },
    )
    for action in ["prepare", "run", "validate"]:
        assert call("diagnostics", action, cfg) == 0, capsys.readouterr().out
    result = json.loads(
        (tmp_path / "results/diagnostics/20250901T000000Z/summary.json").read_text()
    )
    assert result["departures"]["background/airTemperature"]["bias"] == 3
    assert result["departures"]["analysis/airTemperature"]["rmse"] == pytest.approx(
        np.sqrt(2.5)
    )


def test_simpleworkflow_can_load_export(tmp_path, capsys):
    pytest.importorskip("simpleworkflow")
    from simpleworkflow.config import load_workflow

    cfg = case(tmp_path)
    campaign = write(
        tmp_path / "campaign.yaml",
        {
            "schema_version": 1,
            "experiment": str(cfg),
            "calendar": {"start": T, "end": T, "interval": "PT6H"},
            "operations": ["mpas"],
            "output": "wf.yaml",
        },
    )
    from monan_jedi_workflow.platform_cli import main

    assert main("campaign", ["export", str(campaign), "--json"]) == 0
    assert len(load_workflow(tmp_path / "wf.yaml")["tasks"]) == 3


def test_no_reprepare_over_foreign_runtime(tmp_path, capsys):
    cfg = case(tmp_path)
    run = tmp_path / "results/forecast/20250901T000000Z"
    run.mkdir(parents=True)
    (run / "precious.nc").write_text("preserve")
    assert call("mpas", "prepare", cfg) != 0
    assert (run / "precious.nc").read_text() == "preserve"


def test_validate_refuses_changed_inputs(tmp_path, capsys):
    cfg = case(tmp_path)
    for action in ["prepare", "run"]:
        assert call("mpas", action, cfg) == 0
    (tmp_path / "science/forecast.py").write_text("changed")
    assert call("mpas", "validate", cfg) != 0


def test_acquisition_retry_preserves_already_acquired_sources(tmp_path, capsys):
    first = tmp_path / "first"
    first.write_text("one")
    second = tmp_path / "second"
    second.write_text("two")
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "retry", "destination": "results"},
            "observations": {
                "acquisition": {
                    "sources": [
                        {"name": "a", "source": str(first), "destination": "a"},
                        {"name": "b", "source": str(second), "destination": "b"},
                    ]
                }
            },
        },
    )
    from monan_jedi_workflow.platform_cli import main

    def args(a):
        return ["acquire", a, str(cfg), "--cycle", T, "--json"]

    assert main("obs", args("prepare")) == 0
    # A foreign file blocks publication of B after A has already been published.
    (tmp_path / "results/b").write_text("foreign")
    assert main("obs", args("run")) != 0
    (tmp_path / "results/b").unlink()
    assert main("obs", args("run")) == 0, capsys.readouterr().out


def test_native_application_composes_selected_observer_and_filters(tmp_path, capsys):
    from monan_jedi_workflow.platform_config import load_operation
    from monan_jedi_workflow.domain_cli import parse_request

    plugin = tmp_path / "plugins"
    (plugin / "da/base").mkdir(parents=True)
    (plugin / "da/filters").mkdir(parents=True)
    (plugin / "anchors.yaml").write_text("shared: &limit 3\n")
    (plugin / "da/base/sondes.yaml").write_text(
        "obs space:\n  name: Radiosonde\nobs operator:\n  name: VertInterp\n"
    )
    (plugin / "da/filters/sondes.yaml").write_text(
        "obs filters:\n  - filter: Background Check\n    threshold: *limit\n"
    )
    write(
        tmp_path / "application.yaml",
        {
            "cost function": {
                "cost type": "3D-FGAT",
                "observations": {"observers": []},
            },
            "variational": {"iterations": [{"ninner": 10}]},
        },
    )
    write(
        tmp_path / "jedi.yaml",
        {
            "jedi": {
                "run_dir": "jedi/{cycle_id}",
                "application": "application.yaml",
                "application_overrides": {
                    "variational": {"iterations": [{"ninner": 20}]}
                },
            },
            "observations": {
                "configure": "plugins",
                "anchors": ["anchors.yaml"],
                "use": ["sondes"],
            },
        },
    )
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "composition", "destination": "results"},
            "jedi": "jedi.yaml",
        },
    )
    op = load_operation(parse_request("jedi", ["inspect", str(cfg), "--cycle", T]))
    app = op.section["_resolved_application"]
    assert (
        app["cost function"]["observations"]["observers"][0]["obs filters"][0][
            "threshold"
        ]
        == 3
    )
    assert app["variational"]["iterations"] == [{"ninner": 20}]
    assert not (tmp_path / "results").exists()


def test_packaged_fixture_single_cycle(tmp_path, capsys):
    import shutil
    from monan_jedi_workflow.platform_cli import main

    example = Path(__file__).resolve().parents[1] / "examples/beta/experiment.yaml"
    cfg = tmp_path / "experiment.yaml"
    shutil.copyfile(example, cfg)
    for app, prefix in [
        ("obs", ["acquire"]),
        ("obs", ["convert"]),
        ("jedi", []),
        ("mpas", []),
        ("diagnostics", []),
    ]:
        for action in ["prepare", "run", "validate"]:
            assert (
                main(app, [*prefix, action, str(cfg), "--cycle", T, "--json"]) == 0
            ), capsys.readouterr().out


def test_campaign_exclusive_end(tmp_path, capsys):
    cfg = case(tmp_path)
    path = write(
        tmp_path / "campaign.yaml",
        {
            "schema_version": 1,
            "experiment": str(cfg),
            "calendar": {
                "start": T,
                "end": "2025-09-01T06:00:00Z",
                "interval": "PT6H",
                "end_inclusive": False,
            },
            "operations": ["mpas"],
        },
    )
    from monan_jedi_workflow.platform_cli import main

    assert main("campaign", ["inspect", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["cycles"] == 1


def test_init_validates_runtime_relative_outputs(tmp_path, capsys):
    cfg = case(tmp_path)
    data = yaml.safe_load((tmp_path / "science/forecast.yaml").read_text())
    data["mpas_init"] = {**data["mpas"], "run_dir": "init/{cycle_id}"}
    write(tmp_path / "science/forecast.yaml", data)
    from monan_jedi_workflow.platform_cli import main

    for action in ["prepare", "run", "validate"]:
        assert (
            main("mpas", ["init", action, str(cfg), "--cycle", T, "--json"]) == 0
        ), capsys.readouterr().out


def test_converter_script_change_invalidates_prepared_operation(tmp_path, capsys):
    source = tmp_path / "input"
    source.write_text("source")
    driver = tmp_path / "convert.py"
    driver.write_text("print('original')")
    write(
        tmp_path / "obs.yaml",
        {
            "obs2ioda": {
                "work_dir": "obs/{cycle_id}",
                "inspection": {"argv": ["echo", "IODA"]},
                "converters": [
                    {
                        "name": "sondes",
                        "inputs": [str(source)],
                        "outputs": ["{work_dir}/obs.h5"],
                        "argv": [sys.executable, str(driver)],
                    }
                ],
            }
        },
    )
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "obs", "destination": "results"},
            "observations": "obs.yaml",
        },
    )
    from monan_jedi_workflow.platform_cli import main

    def args(a):
        return ["convert", a, str(cfg), "--cycle", T, "--json"]

    assert main("obs", args("prepare")) == 0
    driver.write_text("print('changed')")
    assert main("obs", args("run")) != 0
    assert "changed" in capsys.readouterr().out


def test_link_directory_asset_change_invalidates_reuse(tmp_path, capsys):
    cfg = case(tmp_path)
    source = tmp_path / "science/static"
    source.mkdir()
    asset = source / "physics.tbl"
    asset.write_text("one")
    data = yaml.safe_load((tmp_path / "science/forecast.yaml").read_text())
    data["mpas"]["link_directories"] = [
        {"source": "static", "include": ["physics.tbl"]}
    ]
    write(tmp_path / "science/forecast.yaml", data)
    assert call("mpas", "prepare", cfg) == 0
    asset.write_text("two")
    assert call("mpas", "run", cfg) != 0
    assert "changed" in capsys.readouterr().out


def test_failed_converter_cannot_be_reused_as_success(tmp_path, capsys):
    driver = tmp_path / "fail.py"
    driver.write_text(
        "from pathlib import Path\nPath('obs.h5').write_text('partial')\nraise SystemExit(1)\n"
    )
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "fail", "destination": "results"},
            "observations": {
                "obs2ioda": {
                    "work_dir": "obs/{cycle_id}",
                    "inspection": {"argv": ["echo", "IODA"]},
                    "converters": [
                        {
                            "name": "sondes",
                            "inputs": [],
                            "outputs": ["{work_dir}/obs.h5"],
                            "argv": [sys.executable, str(driver)],
                        }
                    ],
                }
            },
        },
    )
    from monan_jedi_workflow.platform_cli import main

    def args(a):
        return ["convert", a, str(cfg), "--cycle", T, "--json"]

    assert main("obs", args("prepare")) == 0
    assert main("obs", args("run")) != 0
    assert main("obs", args("run")) != 0
    assert main("obs", args("validate")) != 0


def test_diagnostics_refuses_foreign_runtime(tmp_path, capsys):
    log = tmp_path / "log"
    log.write_text("J = 1")
    runtime = tmp_path / "results/diagnostics/20250901T000000Z"
    runtime.mkdir(parents=True)
    (runtime / "summary.json").write_text("FOREIGN")
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "diag", "destination": "results"},
            "diagnostics": {
                "run_dir": "diagnostics/{cycle_id}",
                "cost_function": {"log": str(log)},
            },
        },
    )
    assert call("diagnostics", "prepare", cfg) != 0
    assert (runtime / "summary.json").read_text() == "FOREIGN"


def test_same_resolved_runtime_cannot_have_two_owners(tmp_path, capsys):
    first = case(tmp_path)
    assert call("mpas", "prepare", first) == 0
    second = tmp_path / "second.yaml"
    data = yaml.safe_load(first.read_text())
    data["experiment"]["destination"] = "other"
    native = yaml.safe_load((tmp_path / "science/forecast.yaml").read_text())
    native["mpas"]["run_dir"] = str(tmp_path / "results/forecast/{cycle_id}")
    write(tmp_path / "science/forecast.yaml", native)
    write(second, data)
    assert call("mpas", "prepare", second) != 0


def test_unselected_converter_environment_does_not_block_selected_source(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.delenv("UNSELECTED_TOOL", raising=False)
    cfg = write(
        tmp_path / "experiment.yaml",
        {
            "schema_version": 1,
            "experiment": {"name": "subset", "destination": "results"},
            "observations": "obs.yaml",
        },
    )
    write(
        tmp_path / "obs.yaml",
        {
            "observations": {
                "use": ["sondes"],
                "products": {"sondes": {"converter": "prepbufr"}},
            },
            "obs2ioda": {
                "work_dir": "obs/{cycle_id}",
                "inspection": {"argv": ["echo", "IODA"]},
                "converters": [
                    {
                        "name": "prepbufr",
                        "inputs": [],
                        "outputs": ["{work_dir}/obs.h5"],
                        "argv": ["echo", "convert"],
                    },
                    {
                        "name": "ascat",
                        "inputs": [],
                        "outputs": ["{work_dir}/unused.h5"],
                        "argv": ["${UNSELECTED_TOOL}"],
                    },
                ],
            },
        },
    )
    from monan_jedi_workflow.platform_cli import main

    assert (
        main("obs", ["convert", "check", str(cfg), "--cycle", T, "--json"]) == 0
    ), capsys.readouterr().out


def test_campaign_initialization_is_exported_once(tmp_path, capsys):
    cfg = case(tmp_path)
    native = yaml.safe_load((tmp_path / "science/forecast.yaml").read_text())
    native["mpas_init"] = {**native["mpas"], "run_dir": "init/{cycle_id}"}
    write(tmp_path / "science/forecast.yaml", native)
    config = write(
        tmp_path / "campaign.yaml",
        {
            "schema_version": 1,
            "experiment": str(cfg),
            "calendar": {"start": T, "end": "2025-09-01T06:00:00Z", "interval": "PT6H"},
            "initialization": [
                {"operation": "mpas.init", "cycle": "2025-08-31T18:00:00Z"}
            ],
            "operations": ["mpas"],
            "output": "workflow.yaml",
        },
    )
    from monan_jedi_workflow.platform_cli import main

    assert main("campaign", ["export", str(config), "--json"]) == 0
    document = yaml.safe_load((tmp_path / "workflow.yaml").read_text())
    assert len(document["initialization"]["tasks"]) == 3
    assert len(document["tasks"]) == 6


def test_unrelated_site_variable_not_required_by_forecast(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.delenv("MISSING_BMATRIX", raising=False)
    cfg = case(tmp_path)
    data = yaml.safe_load(cfg.read_text())
    data["site"]["variables"] = {"bmatrix_root": "${MISSING_BMATRIX}"}
    write(cfg, data)
    assert call("mpas", "check", cfg) == 0, capsys.readouterr().out


def test_unfinished_attempt_is_not_silently_reexecuted(tmp_path, capsys):
    cfg = case(tmp_path)
    assert call("mpas", "prepare", cfg) == 0
    state_path = (
        tmp_path / "results/.platform/20250901T000000Z/mpas-forecast/state.json"
    )
    state = json.loads(state_path.read_text())
    state["state"] = "running"
    state_path.write_text(json.dumps(state))
    assert call("mpas", "run", cfg) != 0
    assert "unfinished" in capsys.readouterr().out
