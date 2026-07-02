"""Tests for V2 MPAS initialization."""

from __future__ import annotations

import sys
from pathlib import Path

from monan_jedi_workflow.components.model.mpas import compile_mpas_initialization
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
