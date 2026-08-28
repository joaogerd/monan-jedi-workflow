import pytest

from monan_jedi_workflow.pbs_directives import pbs_header_lines


@pytest.mark.parametrize("queue", ["pesqmini", "pesqmidi", "  pesqmini\t"])
def test_compute_queue_requests_exclusive_placement_once(queue: str) -> None:
    lines = pbs_header_lines(
        job_name="test",
        queue=queue,
        select=1,
        ncpus=128,
        mpiprocs=128,
        walltime="00:30:00",
    )

    assert lines.count("#PBS -l place=excl") == 1


def test_aux_queue_with_whitespace_omits_exclusive_placement() -> None:
    lines = pbs_header_lines(
        job_name="test",
        queue="  aux\t",
        select=1,
        ncpus=1,
        mpiprocs=1,
        walltime="00:10:00",
    )

    assert "#PBS -q aux" in lines
    assert "#PBS -l place=excl" not in lines


def test_repeated_render_does_not_duplicate_exclusive_placement() -> None:
    arguments = {
        "job_name": "test",
        "queue": "pesqmini",
        "select": 1,
        "ncpus": 128,
        "mpiprocs": 128,
        "walltime": "00:30:00",
    }

    first = pbs_header_lines(**arguments)
    second = pbs_header_lines(**arguments)

    assert first == second
    assert second.count("#PBS -l place=excl") == 1
