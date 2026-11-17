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
        "#PBS -V",  # Forward the configured login-node scientific runtime.
    ]
    if normalized_queue.casefold() != "aux":
        lines.append("#PBS -l place=excl")
    lines.append(f"#PBS -l walltime={walltime}")
    return lines


def pbs_runtime_library_lines() -> list[str]:
    """Make the declared libfabric runtime visible to native PBS applications.

    MONAN_LIBFABRIC_ROOT must point to a directory of a compatible scientific
    runtime. It is provided through PBS -V; no personal hardcoded paths.
    This is shell-only and never launches a Python runtime on a compute node.
    """
    return [
        '# Preserve the site-provided MPI runtime, including Cray libfabric.',
        'if [[ -n "${MONAN_LIBFABRIC_ROOT:-}" ]]; then',
        '  if [[ ! -r "$MONAN_LIBFABRIC_ROOT/libfabric.so.1" ]]; then',
        '    echo "[FALHA] MONAN_LIBFABRIC_ROOT nao contem libfabric.so.1 acessivel: $MONAN_LIBFABRIC_ROOT" >&2',
        '    exit 127',
        '  fi',
        '  export LD_LIBRARY_PATH="$MONAN_LIBFABRIC_ROOT${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"',
        'fi',
    ]
