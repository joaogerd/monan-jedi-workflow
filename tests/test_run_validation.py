from __future__ import annotations

import json
from pathlib import Path

from monan_jedi_workflow.config import ExperimentConfig
from monan_jedi_workflow.run_validation import validate_run
from monan_jedi_workflow.scheduler import manifest_path


def make_config(tmp_path: Path) -> ExperimentConfig:
    return ExperimentConfig(
        root=tmp_path,
        experiment={"experiment": {"name": "case"}, "paths": {"work_root": str(tmp_path), "runtime_dir": "runtime", "rendered_dir": "rendered"}},
        runtime={}, variables={}, observations={},
        pbs={"pbs": {"log": {"directory": "logs", "filename": "run.${NP}.${PBS_JOBID}.log"}}},
        validation={"validation": {"run": {
            "required_log_markers": ["with status = 0", "OOPS Ending"],
            "warning_log_markers": ["[CRAYBLAS_WARNING]"],
            "required_outputs": ["Data/states/analysis.nc", "Data/os/obs.nc4"],
        }}},
    )


def test_validate_run_uses_job_specific_log_and_outputs(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    runtime = tmp_path / "runtime"
    (runtime / "logs").mkdir(parents=True)
    (runtime / "Data/states").mkdir(parents=True)
    (runtime / "Data/os").mkdir(parents=True)
    (runtime / "logs/run.64.123.server.log").write_text("with status = 0\nOOPS Ending\n[CRAYBLAS_WARNING]\n")
    (runtime / "Data/states/analysis.nc").write_bytes(b"state")
    (runtime / "Data/os/obs.nc4").write_bytes(b"obs")
    submission = manifest_path(config)
    submission.parent.mkdir(parents=True)
    submission.write_text(json.dumps({"job_id": "123.server"}))
    report = json.loads(validate_run(config).read_text())
    assert report["valid"] is True
    assert report["warning_marker_counts"]["[CRAYBLAS_WARNING]"] == 1
