"""Tests for V2 JACI platform configuration."""

from __future__ import annotations

from monan_jedi_workflow.platforms.base import ExecutionRequest, ExecutionResources
from monan_jedi_workflow.platforms.jaci.backend import JaciPlatformBackend
from monan_jedi_workflow.platforms.jaci_config import jaci_backend_factory


def test_jaci_backend_factory_resolves_site_policy_from_abstract_resources(tmp_path) -> None:
    """Queue, PBS placement, launcher, and threads must come from JACI policy."""
    config = {
        "platform": {
            "jaci": {
                "scheduler": {
                    "common": {"poll_seconds": 15},
                    "initialization": {"queue": "pesqmini", "cores_per_node": 128, "max_mpi_ranks_per_node": 128},
                    "forecast": {"queue": "pesqmidi", "cores_per_node": 128, "max_mpi_ranks_per_node": 128},
                },
                "mpi_launcher": {"argv": ["/opt/cray/pals/1.6/bin/mpiexec", "-n", "{mpi_ranks}"]},
                "environment": {"prelude": ["module load test"], "variables": {"FI_CXI_RX_MATCH_MODE": "hybrid"}},
                "filesystem": {"allowed_workspace_roots": [str(tmp_path)]},
            }
        }
    }
    backend = jaci_backend_factory(config, stage_kind="initialization")("mpas_init_test")
    assert isinstance(backend, JaciPlatformBackend)
    request = ExecutionRequest(
        ("/bin/true",),
        tmp_path / "run",
        resources=ExecutionResources(mpi_ranks=64, threads_per_rank=2, walltime="00:20:00"),
    )

    plan = backend.resolve(request)
    assert plan.resources.queue == "pesqmini"
    assert plan.resources.select == 1
    assert plan.resources.ncpus == 128
    assert plan.resources.mpiprocs == 64
    assert plan.request.argv[:3] == ("/opt/cray/pals/1.6/bin/mpiexec", "-n", "64")
    assert plan.request.environment["OMP_NUM_THREADS"] == "2"
    assert plan.request.environment["FI_CXI_RX_MATCH_MODE"] == "hybrid"
    assert plan.script.is_file()
