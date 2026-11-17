"""Common PBS directive rendering rules."""

from __future__ import annotations

import shlex


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


def pbs_linker_preflight_lines(executable: str) -> list[str]:
    """Check ELF dependencies once before launching every MPI rank.

    Preserves native-only compute execution. A single clear stderr message
    replaces hundreds of identical dynamic loader errors.
    """
    if not isinstance(executable, str) or not executable:
        raise ValueError("PBS scientific executable must be a nonempty string")
    quoted = shlex.quote(executable)
    return [
        "# Validate native shared libraries after loading the site modules.",
        "if command -v ldd >/dev/null 2>&1; then",
        f'  _monan_missing_libs="$(ldd {quoted} 2>&1 | grep "not found" || true)"',
        '  if [[ -n "$_monan_missing_libs" ]]; then',
        '    echo "[FALHA] O executavel cientifico nao encontra bibliotecas no ambiente PBS:" >&2',
        '    echo "$_monan_missing_libs" >&2',
        '    echo "[ACAO] Revise o perfil de modulos/spack-stack configurado em pbs.site_config." >&2',
        '    exit 127',
        '  fi',
        '  unset _monan_missing_libs',
        'fi',
    ]
