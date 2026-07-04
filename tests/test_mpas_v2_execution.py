"""MPAS V2 local execution tests."""

import sys
from pathlib import Path

from monan_jedi_workflow.components.model.mpas import MpasForecastProduct, MpasForecastStage, MpasOutputContract
from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.core.workflow_spec import WorkflowSpec
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner
from monan_jedi_workflow.platforms.base import ExecutionRequest
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def test_local_backend_runs_and_validates_mpas_products(tmp_path: Path) -> None:
    """A backend completion is followed by restart/state artifact validation."""
    run_dir = tmp_path / "run"
    restart = tmp_path / "products/restart.nc"
    state = tmp_path / "products/mpasout.nc"
    program = tmp_path / "fake_mpas.py"
    program.write_text(
        "from pathlib import Path\nimport sys\nfor item in sys.argv[1:]:\n p=Path(item); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'x')\nprint('MPAS complete')\n",
        encoding="utf-8",
    )
    product = MpasForecastProduct("2026-06-20T00:00:00Z", 48, restart, state)
    request = ExecutionRequest((sys.executable, str(program), str(restart), str(state)), run_dir)
    stage = MpasForecastStage(product, run_dir, MpasOutputContract((), Path("stdout.log"), ("MPAS complete",)), request=request, backend=LocalProcessBackend())
    context = RunContext("bmatrix", "mpas-local", tmp_path / "workspace", config={})
    runner = LocalWorkflowRunner(WorkflowSpec.from_stages("bmatrix", [stage.spec]), {stage.spec.name: stage})

    assert len(runner.run(context)) == 1
    assert restart.is_file() and state.is_file()
    assert runner.run(context) == ()
