"""Adapters for existing scientific stage APIs; no scheduler submission."""

from pathlib import Path
import json
import os
import shlex
import subprocess
import yaml
from .platform_state import atomic_json
from .stage_config import render_text


def native_functions(key):
    if key == "jedi":
        from .jedi_stage import load_jedi_run, prepare_jedi, validate_jedi

        return load_jedi_run, prepare_jedi, validate_jedi
    if key == "mpas":
        from .mpas_stage import load_mpas_run, prepare_mpas, validate_mpas

        return load_mpas_run, prepare_mpas, validate_mpas
    if key == "mpas_init":
        from .init_stage import _load, prepare_mpas_init, validate_mpas_init

        return _load, prepare_mpas_init, validate_mpas_init
    if key == "obs2ioda":
        from .obs2ioda_stage import load_obs2ioda_run, validate_obs2ioda
        from .obs_cycle_stage import prepare_obs2ioda_resolved

        return load_obs2ioda_run, prepare_obs2ioda_resolved, validate_obs2ioda
    raise ValueError(f"unsupported native stage: {key}")


def materialize(op, directory):
    directory.mkdir(parents=True, exist_ok=True)
    from copy import deepcopy

    section = deepcopy(op.section)
    if "_resolved_application" in section:
        application = section.pop("_resolved_application")
        target = section.pop("_application_target")
        template = directory / "application.resolved.yaml.in"
        content = yaml.safe_dump(application, sort_keys=False)
        # Keep ordinary YAML braces literal for the native str.format renderer.
        import re

        fields = {}

        def save(match):
            token = f"PLATFORMFIELD{len(fields)}TOKEN"
            fields[token] = match.group()
            return token

        content = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", save, content)
        content = content.replace("{", "{{").replace("}", "}}")
        for token, value in fields.items():
            content = content.replace(token, value)
        template.write_text(content)
        templates = [v for v in section.get("templates", []) if v["target"] != target]
        section["templates"] = [{"source": str(template), "target": target}, *templates]
    path = directory / op.filename
    path.write_text(yaml.safe_dump({op.key: section}, sort_keys=False))
    atomic_json(
        directory / "provenance.json", {"sources": op.sources, "identity": op.identity}
    )
    return directory


def render_run(op, request, directory):
    loader, _, _ = native_functions(op.key)
    return loader(directory, request.cycle)


def paths(run):
    return getattr(run, "run_dir", getattr(run, "work_dir", None))


def execute_native(op, request, directory):
    run = render_run(op, request, directory)
    if op.key == "obs2ioda":
        from .obs_cycle_stage import run_obs2ioda_resolved

        return run_obs2ioda_resolved(directory, request.cycle, force=True)
    mode = op.site.get("execution", {}).get("mode", "pbs")
    if mode not in {"local", "pbs"}:
        raise ValueError("site.execution.mode must be local or pbs")
    if mode == "pbs" and not os.environ.get("PBS_JOBID"):
        raise RuntimeError(
            "PBS worker requires an existing allocation (PBS_JOBID); run does not submit jobs"
        )
    cfg = run.config["pbs"]
    if mode == "local":
        if int(cfg.get("mpiprocs", 1)) != 1:
            raise ValueError(
                "local sequential execution requires mpiprocs=1; use a PBS allocation for MPI"
            )
        lines = ["set -euo pipefail"]
        lines += [
            render_text(v, run.context, label="pbs.bootstrap")
            for v in cfg.get("bootstrap", [])
        ]
        lines += [
            "source " + shlex.quote(render_text(v, run.context, label="pbs.setup"))
            for v in cfg.get("setup", [])
        ]
        for name, value in cfg.get("environment", {}).items():
            if not name.replace("_", "a").isalnum() or name[0].isdigit():
                raise ValueError("invalid environment name")
            lines += [
                f"export {name}="
                + shlex.quote(
                    render_text(str(value), run.context, label="pbs.environment")
                )
            ]
        lines += [
            shlex.join(
                [
                    render_text(v, run.context, label="pbs.command")
                    for v in cfg["command"]
                ]
            )
        ]
        command = ["bash", "-c", "\n".join(lines)]
    else:
        command = ["bash", str(run.pbs_path)]
    stdout = paths(run) / render_text(
        cfg.get("stdout", "jedi.stdout.log" if op.key == "jedi" else "stdout.log"),
        run.context,
        label="pbs.stdout",
    )
    stderr = paths(run) / render_text(
        cfg.get("stderr", "jedi.stderr.log" if op.key == "jedi" else "stderr.log"),
        run.context,
        label="pbs.stderr",
    )
    existing = [p for p in (stdout, stderr) if p.is_file()]
    if existing:
        import tempfile
        import shutil

        archive_root = paths(run) / ".platform" / "previous-logs"
        archive_root.mkdir(parents=True, exist_ok=True)
        archive = Path(tempfile.mkdtemp(dir=archive_root, prefix="attempt-"))
        for index, path in enumerate(existing):
            shutil.copyfile(path, archive / f"{index}-{path.name}")
    stdout.parent.mkdir(parents=True, exist_ok=True)
    stderr.parent.mkdir(parents=True, exist_ok=True)
    with stdout.open("w") as out, stderr.open("w") as err:
        result = subprocess.run(
            command, cwd=paths(run), stdout=out, stderr=err, check=False
        )
    manifest = json.loads(run.manifest_path.read_text())
    manifest.update(
        {
            "execution_backend": "worker",
            "worker_completed": result.returncode == 0,
            "worker_returncode": result.returncode,
            "state": "worker-finished" if result.returncode == 0 else "failed",
        }
    )
    atomic_json(run.manifest_path, manifest)
    if result.returncode:
        raise RuntimeError(f"{op.key} exited {result.returncode}; see {stderr}")
    return run.manifest_path
