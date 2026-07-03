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


def test_initialization_preparation_renders_mesh_output_and_geodata(tmp_path: Path) -> None:
    """WPS forcing must use declared mesh, output names, and local geodata."""
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
 config_fg_interval = 0
 config_block_decomp_file_prefix = 'x1.40962.graph.info.part.'
/
""",
        encoding="utf-8",
    )
    grid = tmp_path / "inputs/x1.10242.grid.nc"
    grid.parent.mkdir(parents=True)
    grid.write_bytes(b"grid")
    forcing = tmp_path / "wps/FILE:2026-06-20_00"
    forcing.parent.mkdir(parents=True)
    forcing.write_bytes(b"wps")
    geog = tmp_path / "geog"
    (geog / "topo_gmted2010_30s").mkdir(parents=True)
    (geog / "topo_gmted2010_30s/index").write_text("index", encoding="utf-8")
    config = {
        "model": {
            "mpas": {
                "initialization_products": {
                    "root": str(tmp_path / "products"),
                    "state_template": "{init_yyyymmddhh}/x1.10242.init.{mpas_valid_file_time}.nc",
                },
                "initialization": {
                    "run_dir": "runs/init/{init_yyyymmddhh}",
                    "argv": ["/bin/true"],
                    "geog_data_path": str(geog),
                    "geog_required_datasets": ["topo_gmted2010_30s"],
                    "links": [{"source": str(grid), "target": "x1.10242.grid.nc"}],
                    "templates": [
                        {"source": str(streams), "target": "streams.init_atmosphere"},
                        {"source": str(namelist), "target": "namelist.init_atmosphere"},
                    ],
                },
            }
        }
    }
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

    root = ElementTree.parse(stage.run_dir / "streams.init_atmosphere").getroot()
    input_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "input")
    output_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "output")
    ugwp_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "ugwp_oro_data")
    surface_stream = next(item for item in root.iter("immutable_stream") if item.get("name") == "surface")
    assert input_stream.get("filename_template") == "x1.10242.grid.nc"
    assert input_stream.get("filename_template") != "FILE:2026-06-20_00"
    assert output_stream.get("filename_template") == "x1.10242.init.2026-06-20_00.00.00.nc"
    assert output_stream.get("filename_template") != "x1.40962.init.nc"
    assert ugwp_stream.get("filename_template") == "x1.10242.ugwp_oro_data.nc"
    assert surface_stream.get("filename_template") == "x1.10242.sfc_update.nc"
    assert (stage.run_dir / "FILE:2026-06-20_00").is_symlink()
    rendered = (stage.run_dir / "namelist.init_atmosphere").read_text(encoding="utf-8")
    assert f"config_geog_data_path = '{geog}/'" in rendered


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
