"""Tests for V2 MPAS initialization."""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree

from monan_jedi_workflow.components.model.mpas import compile_mpas_initialization
from monan_jedi_workflow.components.model.mpas.staging import LinkSpec
from monan_jedi_workflow.core.config import load_mapping
from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.core.workflow_spec import WorkflowSpec
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def test_documented_initialization_example_compiles(tmp_path: Path) -> None:
    """The public initialization example must remain compiler-compatible."""
    config = load_mapping(Path("examples/v2/model/mpas_initialization.yaml.example"))
    stage = compile_mpas_initialization(
        config,
        workspace=tmp_path,
        cycle_time="2026-06-20T00:00:00Z",
        backend=LocalProcessBackend(),
    )
    assert stage.product.cycle_time == "2026-06-20_00:00:00"


def test_initialization_stage_runs_and_publishes_state(tmp_path: Path) -> None:
    """A configured initialization must publish and validate its state artifact."""
    program = tmp_path / "fake_init.py"
    program.write_text(
        "from pathlib import Path\nimport sys\npath=Path(sys.argv[1]); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'init'); print('Initialization complete')\n",
        encoding="utf-8",
    )
    config = {
        "model": {
            "mpas": {
                "initialization_products": {
                    "root": str(tmp_path / "products"),
                    "state_template": "{init_yyyymmddhh}/init.{mpas_valid_file_time}.nc",
                },
                "initialization": {
                    "run_dir": "runs/init/{init_yyyymmddhh}",
                    "argv": [sys.executable, "{workspace}/fake_init.py", "{state}"],
                    "validation": {
                        "log": "stdout.log",
                        "required_log_markers": ["Initialization complete"],
                    },
                },
            }
        }
    }
    context = RunContext("bmatrix", "init-local", tmp_path, config=config)
    stage = compile_mpas_initialization(
        config,
        workspace=tmp_path,
        cycle_time="2026-06-20T00:00:00Z",
        backend=LocalProcessBackend(),
    )
    runner = LocalWorkflowRunner(
        WorkflowSpec.from_stages("bmatrix", [stage.spec]),
        {stage.spec.name: stage},
    )

    assert len(runner.run(context)) == 1
    assert stage.product.state.is_file()
    assert runner.run(context) == ()


def _init_templates(tmp_path: Path) -> tuple[Path, Path]:
    """Create minimal installed-style init templates used by WPS-backed tests."""
    streams = tmp_path / "streams.init.in"
    streams.write_text(
        """<streams>
<immutable_stream name="input" type="input" filename_template="wrong-grid.nc" input_interval="initial_only" />
<immutable_stream name="output" type="output" filename_template="x1.40962.init.nc" output_interval="initial_only" />
<immutable_stream name="ugwp_oro_data" type="output" filename_template="x1.40962.ugwp_oro_data.nc" output_interval="initial_only" />
<immutable_stream name="surface" type="output" filename_template="x1.40962.sfc_update.nc" output_interval="86400" />
</streams>""",
        encoding="utf-8",
    )
    namelist = tmp_path / "namelist.init.in"
    namelist.write_text(
        """&nhyd_model
 config_init_case = 0
 config_start_time = '2000-01-01_00:00:00'
 config_stop_time = '2000-01-01_00:00:00'
 config_geog_data_path = '/glade/work/wrfhelp/WPS_GEOG/'
 config_met_prefix = 'UNKNOWN'
 config_sfc_prefix = 'SST'
 config_fg_interval = 0
 config_static_interp = true
 config_native_gwd_static = true
 config_native_gwd_gsl_static = false
 config_vertical_grid = true
 config_met_interp = true
 config_block_decomp_file_prefix = 'x1.40962.graph.info.part.'
/
""",
        encoding="utf-8",
    )
    return streams, namelist


def _wps_init_config(
    tmp_path: Path,
    *,
    bootstrap: Path,
    bootstrap_target: str,
    mode: str,
) -> dict[str, object]:
    """Build one minimal WPS-backed dynamic-init configuration."""
    streams, namelist = _init_templates(tmp_path)
    return {
        "model": {
            "mpas": {
                "initialization_products": {
                    "root": str(tmp_path / "products"),
                    "state_template": "{init_yyyymmddhh}/x1.10242.init.{mpas_valid_file_time}.nc",
                },
                "initialization": {
                    "run_dir": "runs/init/{init_yyyymmddhh}",
                    "argv": ["/bin/true"],
                    "wps_input": {"target": "FILE:{wps_time}"},
                    "static_fields": {
                        "mode": mode,
                        "source": str(bootstrap),
                        "target": bootstrap_target,
                    },
                    "links": [{"source": str(bootstrap), "target": bootstrap_target}],
                    "templates": [
                        {"source": str(streams), "target": "streams.init_atmosphere"},
                        {"source": str(namelist), "target": "namelist.init_atmosphere"},
                    ],
                },
            }
        }
    }


def _prepare_wps_init(
    tmp_path: Path,
    config: dict[str, object],
) -> tuple[RunContext, object, Path]:
    """Compile and prepare one initialization after attaching its upstream FILE input."""
    forcing = tmp_path / "wps/FILE:2026-06-20_00"
    forcing.parent.mkdir(parents=True, exist_ok=True)
    forcing.write_bytes(b"wps")
    context = RunContext("bmatrix", "init-wps", tmp_path, config=config)
    stage = compile_mpas_initialization(
        config,
        workspace=tmp_path,
        cycle_time="2026-06-20T00:00:00Z",
        backend=LocalProcessBackend(),
    )
    stage.links = (*stage.links, LinkSpec(forcing, stage.run_dir / "FILE:2026-06-20_00", upstream_artifact=True))
    stage.values["met_input_filename"] = "FILE:2026-06-20_00"
    stage.values["decomposition_prefix"] = "x1.10242.graph.info.part."
    stage.prepare(context)
    return context, stage, forcing


def test_initialization_preparation_uses_invariant_static_fields(tmp_path: Path) -> None:
    """The historical WPS baseline can use invariant fields as a grid bootstrap."""
    invariant = tmp_path / "inputs/x1.10242.invariant.nc"
    invariant.parent.mkdir(parents=True)
    invariant.write_bytes(b"static")
    config = _wps_init_config(
        tmp_path,
        bootstrap=invariant,
        bootstrap_target="x1.10242.grid.nc",
        mode="invariant",
    )
    _, stage, forcing = _prepare_wps_init(tmp_path, config)

    root = ElementTree.parse(stage.run_dir / "streams.init_atmosphere").getroot()
    input_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "input")
    output_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "output")
    ugwp_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "ugwp_oro_data")
    surface_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "surface")
    assert input_stream.get("filename_template") == "x1.10242.grid.nc"
    assert input_stream.get("filename_template") != "FILE:2026-06-20_00"
    assert output_stream.get("filename_template") == "x1.10242.init.2026-06-20_00.00.00.nc"
    assert ugwp_stream.get("filename_template") == "x1.10242.ugwp_oro_data.nc"
    assert surface_stream.get("filename_template") == "x1.10242.sfc_update.nc"
    assert (stage.run_dir / "x1.10242.grid.nc").resolve() == invariant
    assert (stage.run_dir / "FILE:2026-06-20_00").is_symlink()
    assert forcing.is_file()

    rendered = (stage.run_dir / "namelist.init_atmosphere").read_text(encoding="utf-8")
    assert "config_met_prefix = 'FILE'" in rendered
    assert "config_sfc_prefix = 'FILE'" in rendered
    assert "config_fg_interval = 86400" in rendered
    assert "config_static_interp = .false." in rendered
    assert "config_native_gwd_static = .false." in rendered
    assert "config_native_gwd_gsl_static = .false." in rendered
    assert "config_vertical_grid = .true." in rendered
    assert "config_met_interp = .true." in rendered


def test_initialization_preparation_consumes_validated_static_product(tmp_path: Path) -> None:
    """The CD-CT/NMC dynamic-init contract consumes static.nc, not the raw grid."""
    static = tmp_path / "static/x1.10242.static.nc"
    static.parent.mkdir(parents=True)
    static.write_bytes(b"validated-static")
    config = _wps_init_config(
        tmp_path,
        bootstrap=static,
        bootstrap_target="x1.10242.static.nc",
        mode="static_product",
    )
    _, stage, forcing = _prepare_wps_init(tmp_path, config)

    root = ElementTree.parse(stage.run_dir / "streams.init_atmosphere").getroot()
    input_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "input")
    output_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "output")
    assert input_stream.get("filename_template") == "x1.10242.static.nc"
    assert output_stream.get("filename_template") == "x1.10242.init.2026-06-20_00.00.00.nc"
    assert (stage.run_dir / "x1.10242.static.nc").resolve() == static
    assert (stage.run_dir / "FILE:2026-06-20_00").is_symlink()
    assert forcing.is_file()

    rendered = (stage.run_dir / "namelist.init_atmosphere").read_text(encoding="utf-8")
    assert "config_met_prefix = 'FILE'" in rendered
    assert "config_sfc_prefix = 'SST'" in rendered
    assert "config_fg_interval = 86400" in rendered
    assert "config_static_interp = .false." in rendered
    assert "config_native_gwd_static = .false." in rendered
    assert "config_native_gwd_gsl_static = .false." in rendered
    assert "config_vertical_grid = .true." in rendered
    assert "config_met_interp = .true." in rendered


def test_initialization_tool_page_has_required_sections() -> None:
    """The initialization documentation must follow the V2 tool-page standard."""
    page = Path("docs/tools/model/mpas-initialization.md").read_text(encoding="utf-8")
    required = (
        "## Purpose",
        "## Scientific Context",
        "## When to Use the Tool",
        "## Inputs",
        "## Outputs",
        "## Artifact Contract",
        "## YAML Configuration",
        "## Parameters",
        "## Dependencies",
        "## CLI Usage",
        "## Validation",
        "## FAQ",
        "## References",
    )
    assert all(section in page for section in required)
