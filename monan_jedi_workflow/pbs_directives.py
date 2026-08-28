"""Common PBS directive rendering rules."""

from __future__ import annotations


def pbs_header_lines(
    *,
    job_name: str,
    queue: str,
    select: int,
    ncpus: int,
    mpiprocs: int,
    walltime: str,
) -> list[str]:
    """Return the common PBS header, including JACI placement policy.

    JACI compute-node queues require exclusive placement.  ``aux`` is the
    sole shared-resource exception.  Normalizing the configured queue here
    keeps that policy identical for every stage that renders PBS scripts.
    """
    normalized_queue = queue.strip()
    if not normalized_queue:
        raise ValueError("PBS queue must not be empty or whitespace.")

    lines = [
        "#!/usr/bin/env bash",
        f"#PBS -N {job_name}",
        f"#PBS -q {normalized_queue}",
        f"#PBS -l select={select}:ncpus={ncpus}:mpiprocs={mpiprocs}",
    ]
    if normalized_queue.casefold() != "aux":
        lines.append("#PBS -l place=excl")
    lines.append(f"#PBS -l walltime={walltime}")
    return lines
