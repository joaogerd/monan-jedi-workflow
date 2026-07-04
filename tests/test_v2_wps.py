"""WPS V2 contract tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from monan_jedi_workflow.components.model.wps import WpsConfigurationError, compile_wps_ungrib
from monan_jedi_workflow.core.stage import RunContext
from monan_jedi_workflow.core.workflow_spec import WorkflowSpec
from monan_jedi_workflow.orchestration.local import LocalWorkflowRunner
from monan_jedi_workflow.platforms.local import LocalProcessBackend


def _configuration(tmp_path: Path, grib_target: str = "GRIBFILE.AAA") -> dict[str, object]:
    """Build one compact declared WPS ungrib case."""
    grib = tmp_path / "gfs.grib2"
    grib.write_bytes(b"GRIB")
    writer = tmp_path / "fake_ungrib.py"
    writer.write_text(
        """from pathlib import Path
import sys
product = Path(sys.argv[1])
product.parent.mkdir(parents=True, exist_ok=True)
product.write_bytes(b'WPS FILE')
print('Ungrib complete')
""",
        encoding="utf-8",
    )
    return {
        "model": {
            "wps": {
                "ungrib_products": {
                    "root": str(tmp_path / "wps"),
                    "intermediate_template": "{init_yyyymmddhh}/FILE:{wps_time}",
                },
                "ungrib": {
                    "run_dir": str(tmp_path / "wps" / "{init_yyyymmddhh}"),
                    "argv": [sys.executable, str(writer), "{intermediate}"],
                    "grib_inputs": [{"source": str(grib), "target": grib_target}],
                    "validation": {"log": "stdout.log", "required_log_markers": ["Ungrib complete"]},
                },
            }
        }
    }


def test_ungrib_publishes_explicit_file_product(tmp_path: Path) -> None:
    """Ungrib must publish the exact FILE path declared for the cycle."""
    config = _configuration(tmp_path)
    context = RunContext("bmatrix", "wps", tmp_path / "workspace", config=config)
    stage = compile_wps_ungrib(config, workspace=context.workspace, init_time="2026-06-20T00:00:00Z", backend=LocalProcessBackend())
    runner = LocalWorkflowRunner(WorkflowSpec.from_stages("bmatrix", [stage.spec]), {stage.spec.name: stage})

    assert len(runner.run(context)) == 1
    assert stage.product.intermediate.name == "FILE:2026-06-20_00"
    assert stage.product.intermediate.is_file()
    assert (stage.run_dir / "GRIBFILE.AAA").is_symlink()
    assert runner.run(context) == ()


def test_ungrib_rejects_undeclared_grib_target(tmp_path: Path) -> None:
    """The WPS input contract must use conventional explicit GRIBFILE names."""
    config = _configuration(tmp_path, grib_target="gfs.grib2")
    with pytest.raises(WpsConfigurationError, match="GRIBFILE"):
        compile_wps_ungrib(config, workspace=tmp_path / "workspace", init_time="2026-06-20T00:00:00Z", backend=LocalProcessBackend())
