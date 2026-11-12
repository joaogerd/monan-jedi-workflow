"""Installed domain apps: shared lifecycle, independent scientific operations."""

from __future__ import annotations
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import json
import argparse
import sys
import tempfile
import yaml

from .domain_cli import parse_request
from .platform_config import load_operation
from .platform_state import atomic_json, lock, now, records, ownership


def location(op, request):
    from .cycle_context import parse_cycle_time

    cycle = parse_cycle_time(request.cycle)
    name = request.app + "-" + request.operation
    if request.source:
        if not request.source.replace("_", "").replace("-", "").isalnum():
            raise ValueError("source must be a plain identifier")
        name += "-" + request.source
    return op.root / ".platform" / cycle.cycle_id / name


def selected(op, request):
    if request.source and op.key == "obs2ioda":
        converters = [
            v
            for v in op.section.get("converters", [])
            if v.get("name") == request.source
        ]
        if not converters:
            raise ValueError(f"unknown converter source: {request.source}")
        op.section["converters"] = converters
        # Selection uses its own runtime: concurrent source operations cannot
        # overwrite a shared Obs2IODA plan.
        op.section["work_dir"] += "/" + request.source
    return op


def inspect_native(op, request, directory):
    from .platform_backend import materialize, render_run, paths

    with tempfile.TemporaryDirectory(prefix="monan-inspect-") as temporary:
        run = render_run(op, request, materialize(op, Path(temporary)))
        description = {
            "run_dir": str(paths(run)),
            "configuration": op.section,
            "origin": str(op.domain_file),
            "identity": op.identity,
        }
        inputs = []
        for entry in run.config.get("links", []) + run.config.get("templates", []):
            from .stage_config import resolve_path

            source = resolve_path(
                entry["source"],
                config_dir=run.config_dir,
                context=run.context,
                label="source",
            )
            if not source.is_relative_to(Path(temporary)):
                inputs.append(source)
        if op.key == "jedi":
            from .jedi_stage import _resolve_background

            inputs.append(_resolve_background(run)[0])
            if run.config.get("analysis_base_state"):
                from .stage_config import resolve_path

                inputs.append(
                    resolve_path(
                        run.config["analysis_base_state"]["source"],
                        config_dir=run.config_dir,
                        context=run.context,
                        label="analysis_base_state",
                    )
                )
        if run.config.get("runtime", {}).get("skeleton"):
            from .stage_config import resolve_path

            skeleton = resolve_path(
                run.config["runtime"]["skeleton"],
                config_dir=run.config_dir,
                context=run.context,
                label="runtime.skeleton",
            )
            inputs.append(skeleton)
            if skeleton.is_dir():
                inputs.extend(p for p in skeleton.rglob("*") if p.is_file())
        # Executables and explicitly named command files participate in re-use.
        for argument in run.config.get("pbs", {}).get("command", []):
            from .stage_config import render_text

            candidate = Path(render_text(argument, run.context, label="pbs.command"))
            if candidate.is_absolute() and candidate.is_file():
                inputs.append(candidate)
        if op.key == "obs2ioda":
            from .obs2ioda_stage import _build_plan
            from .obs_cycle_stage import _resolve_plan

            plan, _ = _resolve_plan(run, _build_plan(run))
            inputs += [Path(p) for c in plan["converters"] for p in c["inputs"]]
            description["conversion_plan"] = plan
        for entry in run.config.get("link_directories", []):
            from .stage_config import resolve_path

            value = entry["source"] if isinstance(entry, dict) else entry
            source = resolve_path(
                value,
                config_dir=run.config_dir,
                context=run.context,
                label="link_directories",
            )
            inputs.append(source)
            if isinstance(entry, dict) and "include" in entry:
                inputs.extend(source / name for name in entry["include"])
            elif source.is_dir():
                inputs.extend(p for p in source.iterdir() if p.is_file())
        if op.key == "obs2ioda":
            for converter in description["conversion_plan"]["converters"]:
                commands = [converter["argv"]]
                from .obs2ioda_stage import _render_inspection

                commands += [
                    _render_inspection(run, converter, Path(output))["argv"]
                    for output in converter["outputs"]
                ]
                for command in commands:
                    for argument in command:
                        path = Path(argument)
                        if path.is_absolute() and path.is_file():
                            inputs.append(path)
        expanded_inputs = []
        for path in inputs:
            expanded_inputs.append(path)
            if path.is_dir():
                expanded_inputs.extend(
                    child for child in path.rglob("*") if child.is_file()
                )
        description["inputs"] = [str(v) for v in expanded_inputs]
        return description


def input_records(description):
    return records([v for v in description.get("inputs", []) if not Path(v).is_dir()])


def check_native(op, request, directory):
    description = inspect_native(op, request, directory)
    for path in description["inputs"]:
        if not Path(path).exists():
            raise FileNotFoundError(f"missing input: {path}")
    pbs = op.section.get("pbs", {})
    if pbs:
        command = pbs.get("command")
        if not isinstance(command, list) or not command:
            raise ValueError("pbs.command must be a nonempty argument list")
        # The native preparer checks staged executables; check absolute tools now.
        executable = command[0]
        if (
            "{" not in executable
            and Path(executable).is_absolute()
            and not Path(executable).is_file()
        ):
            raise FileNotFoundError(f"executable missing: {executable}")
    return description


def product_paths(op, request, directory):
    from .platform_backend import render_run, paths
    from .stage_config import render_text

    run = render_run(op, request, directory)
    if op.key == "obs2ioda":
        from .obs2ioda_stage import _build_plan

        return [Path(p) for c in _build_plan(run)["converters"] for p in c["outputs"]]
    result = []
    for value in run.config["validation"]["required_outputs"]:
        if isinstance(value, dict):
            value = value["path"]
        path = Path(render_text(value, run.context, label="output"))
        result.append(path if path.is_absolute() else paths(run) / path)
    return result


def operate(request):
    if request.app == "campaign":
        from .platform_campaign import campaign_action

        return campaign_action(request)
    op = selected(load_operation(request), request)
    directory = location(op, request)
    state_path = directory / "state.json"
    if op.key in {"acquisition", "diagnostics"}:
        from .platform_products import product_operation

        return product_operation(op, request, directory)
    if request.action in {"inspect", "check"}:
        result = (
            inspect_native(op, request, directory)
            if request.action == "inspect"
            else check_native(op, request, directory)
        )
        return {
            **result,
            "state": "inspected" if request.action == "inspect" else "ready",
        }
    state = json.loads(state_path.read_text()) if state_path.is_file() else None
    if request.action == "status":
        return (
            {
                **state,
                "configuration_compatible": state["identity"] == op.identity,
                "current_identity": op.identity,
            }
            if state
            else {"state": "unprepared", "identity": op.identity}
        )
    if state and state["identity"] != op.identity:
        raise RuntimeError(
            "configuration changed: use a new experiment destination; refusing incompatible reuse"
        )
    if request.action != "prepare" and state is None:
        raise RuntimeError("operation is not prepared; run prepare first")
    from .platform_backend import (
        materialize,
        native_functions,
        execute_native,
    )

    runtime = Path(inspect_native(op, request, directory)["run_dir"])
    with (
        lock(directory / "operation.lock"),
        ownership(runtime, directory, claim=request.action == "prepare"),
    ):
        # Re-read after acquiring ownership; a preceding worker may have changed it.
        state = json.loads(state_path.read_text()) if state_path.is_file() else None
        if state and state["identity"] != op.identity:
            raise RuntimeError("configuration changed while waiting for operation")
        if request.action == "prepare":
            if state:
                if state["inputs"] != input_records(
                    inspect_native(op, request, directory)
                ):
                    raise RuntimeError("inputs changed; use a new destination")
                return {**state, "reused": True}
            description = check_native(op, request, directory)
            if op.key == "obs2ioda":
                for converter in description["conversion_plan"]["converters"]:
                    for output in converter["outputs"]:
                        if Path(output).exists():
                            raise FileExistsError(
                                f"refusing existing converter product: {output}"
                            )
            materialize(op, directory / "configuration")
            _, prepare, _ = native_functions(op.key)
            run = prepare(directory / "configuration", request.cycle)
            state = {
                "identity": op.identity,
                "state": "prepared",
                "inputs": input_records(description),
                "prepared_at": now(),
                "run_dir": str(getattr(run, "run_dir", getattr(run, "work_dir", ""))),
                "attempts": [],
            }
            atomic_json(state_path, state)
        elif request.action == "run":
            if state["state"] == "running":
                raise RuntimeError(
                    "previous attempt is unfinished; inspect process/PBS job before using a new destination"
                )
            if state["inputs"] != input_records(inspect_native(op, request, directory)):
                raise RuntimeError("inputs changed after preparation")
            if state["state"] == "validated":
                if (
                    records(product_paths(op, request, directory / "configuration"))
                    != state["products"]
                ):
                    raise RuntimeError("validated products changed")
                return {**state, "reused": True}
            attempt = {"started_at": now()}
            state["attempts"].append(attempt)
            state["state"] = "running"
            atomic_json(state_path, state)
            try:
                execute_native(op, request, directory / "configuration")
            except Exception as error:
                state["state"] = "failed"
                attempt.update(finished_at=now(), error=str(error))
                atomic_json(state_path, state)
                raise
            state["state"] = "finished"
            attempt.update(finished_at=now())
            atomic_json(state_path, state)
        else:
            if state["inputs"] != input_records(inspect_native(op, request, directory)):
                raise RuntimeError("inputs changed after execution")
            if state["state"] not in {"finished", "validated"}:
                raise RuntimeError("validate requires a completed run")
            _, _, validate = native_functions(op.key)
            try:
                report = validate(directory / "configuration", request.cycle)
                state["products"] = records(
                    product_paths(op, request, directory / "configuration")
                )
            except Exception:
                state["state"] = "invalid"
                atomic_json(state_path, state)
                raise
            state.update(state="validated", validation=str(report))
            atomic_json(state_path, state)
        return state


def main(app, argv=None):
    request = parse_request(app, list(sys.argv[1:] if argv is None else argv))
    output = StringIO()
    try:
        with redirect_stdout(output):
            result = operate(request)
        result = {
            "app": app,
            "operation": request.operation,
            "action": request.action,
            "cycle": request.cycle,
            **result,
        }
        if request.json_output:
            print(json.dumps(result, default=str, sort_keys=True))
        else:
            print(
                f"[{result.get('state', 'OK')}] {app}/{request.operation} {request.action} {request.cycle or ''}"
            )
            print(json.dumps(result, indent=2, default=str))
        return 0
    except (
        ValueError,
        OSError,
        RuntimeError,
        KeyError,
        TypeError,
        AttributeError,
        ImportError,
        yaml.YAMLError,
        argparse.ArgumentTypeError,
    ) as error:
        result = {
            "app": app,
            "operation": request.operation,
            "action": request.action,
            "cycle": request.cycle,
            "state": "error",
            "error": str(error),
        }
        print(
            json.dumps(result, default=str),
            file=sys.stdout if request.json_output else sys.stderr,
        )
        return 1


def obs():
    return main("obs")


def jedi():
    return main("jedi")


def mpas():
    return main("mpas")


def diagnostics():
    return main("diagnostics")


def campaign():
    return main("campaign")
