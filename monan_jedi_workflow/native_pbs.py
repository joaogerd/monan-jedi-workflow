"""Submit native scientific commands from the login node, never Python jobs.

This is used by WPS and Obs2IODA when their own configuration requests PBS.
The simpleWorkflow task itself remains executor=local.
"""
from __future__ import annotations

from pathlib import Path
from .pbs_directives import pbs_runtime_library_lines
from .scientific_environment import render_native_site_setup
import os
import re
import shlex
import subprocess
import time

_JOB = re.compile(r"^[0-9]+(?:\.[A-Za-z0-9_.-]+)?$")
_STATE = re.compile(r"(?m)^\s*job_state\s*=\s*([A-Za-z])\s*$")
_EXIT = re.compile(r"(?m)^\s*Exit_status\s*=\s*(-?\d+)\s*$")
_QUEUE = re.compile(r"^[A-Za-z0-9_.-]+$")
_WALL = re.compile(r"^(\d{1,3}):([0-5]\d):([0-5]\d)$")


def native_pbs_run(
    *, name: str, commands: list[list[str]], cwd: Path,
    stdout: Path, stderr: Path, resources: dict, environment: dict[str, str] | None = None,
) -> tuple[str, int]:
    """Run already-resolved native argv via qsub, retaining exact PBS script and logs.

    Never resubmit automatically when the scheduler result is unknown.
    """
    if os.environ.get("PBS_JOBID"):
        raise RuntimeError("Native PBS jobs must be submitted from login, not from another PBS job")
    if not commands or any(not argv or not all(isinstance(x, str) and x for x in argv) for argv in commands):
        raise ValueError("native PBS commands must be nonempty argv lists")
    queue = str(resources.get("queue", ""))
    walltime = str(resources.get("walltime", ""))
    if not _QUEUE.fullmatch(queue) or not _WALL.fullmatch(walltime):
        raise ValueError("native PBS requires a safe queue and HH:MM:SS walltime")
    counts = {}
    for key in ("select", "ncpus", "mpiprocs"):
        value = resources.get(key, 1)
        if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
            raise ValueError(f"native PBS {key} must be a positive integer")
        counts[key] = int(value)
    cwd = Path(cwd).resolve()
    stdout = Path(stdout).resolve()
    stderr = Path(stderr).resolve()
    if not cwd.is_dir():
        raise FileNotFoundError(f"native PBS work directory missing: {cwd}")
    stdout.parent.mkdir(parents=True, exist_ok=True)
    stderr.parent.mkdir(parents=True, exist_ok=True)
    script = cwd / (re.sub(r"[^A-Za-z0-9_.-]", "_", name) + ".native.pbs")
    if script.exists():
        raise FileExistsError(
            f"Native PBS script already exists: {script}; inspect previous job before resubmission"
        )
    lines = [
        "#!/bin/bash",
        "#PBS -N " + re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:60],
        "#PBS -q " + queue,
        f'#PBS -l select={counts["select"]}:ncpus={counts["ncpus"]}:mpiprocs={counts["mpiprocs"]}',
        *(["#PBS -l place=excl"] if queue.casefold() != "aux" else []),
        "#PBS -l walltime=" + walltime,
        # A declared site profile renders its own scientific runtime.
        # Legacy jobs without a profile retain inherited-environment behavior.
        *(["#PBS -V"] if not resources.get("site_config") else []),
        "#PBS -o " + str(stdout),
        "#PBS -e " + str(stderr),
        "set -euo pipefail",
        "cd " + shlex.quote(str(cwd)),
        *render_native_site_setup(resources, config_dir=cwd),
    ]
    for key, value in sorted((environment or {}).items()):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"invalid PBS environment variable {key!r}")
        if key == "LD_LIBRARY_PATH":
            # Preserve libraries loaded by the site/spack-stack module.
            lines.append("export LD_LIBRARY_PATH=" + shlex.quote(str(value)) +
                         "${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}")
        else:
            lines.append("export " + key + "=" + shlex.quote(str(value)))
    if not resources.get("site_config"):
        lines.extend(pbs_runtime_library_lines())
    lines.extend(shlex.join(argv) for argv in commands)
    script.write_text("\n".join(lines) + "\n")
    submitted = subprocess.run(["qsub", str(script)], cwd=cwd, text=True,
                               capture_output=True, check=False)
    if submitted.returncode:
        raise RuntimeError(f"native PBS qsub failed for {name}: {submitted.stderr.strip()}")
    job_id = submitted.stdout.strip().splitlines()[-1].strip() if submitted.stdout.strip() else ""
    if not _JOB.fullmatch(job_id):
        raise RuntimeError("qsub accepted submission but did not return a valid job ID; inspect qstat")
    (script.with_suffix(".jobid")).write_text(job_id + "\n")
    print(f"[PBS] {name}: submitted job {job_id}")
    # Poll job history as well as the active queue. Any ambiguous outcome is
    # treated as failure and must be inspected before trying again.
    max_seconds = (int(_WALL.fullmatch(walltime)[1]) * 3600
                   + int(_WALL.fullmatch(walltime)[2]) * 60
                   + int(_WALL.fullmatch(walltime)[3]) + 1200)
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        result = subprocess.run(["qstat", "-xf", job_id], text=True,
                                capture_output=True, check=False, timeout=30)
        if result.returncode == 0:
            state = _STATE.search(result.stdout)
            if state and state[1] in {"F", "X"}:
                exit_status = _EXIT.search(result.stdout)
                if exit_status is None:
                    raise RuntimeError(f"PBS {job_id} finished without Exit_status; inspect manually")
                code = int(exit_status[1])
                if code:
                    raise RuntimeError(f"PBS {job_id} failed with Exit_status={code}; see {stderr}")
                return job_id, code
        time.sleep(5)
    raise TimeoutError(f"PBS job {job_id} outcome not confirmed; inspect qstat before retrying")
