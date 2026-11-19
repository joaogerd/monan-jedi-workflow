"""Acquisition and diagnostics with the same explicit operation lifecycle."""

from pathlib import Path
import csv
import json
import os
import re
import shutil
import tempfile
import urllib.request

from .cycle_context import parse_cycle_time
from .platform_state import atomic_json, lock, records, now, ownership
from contextlib import nullcontext


def resolve(value, op, request, *, output=False):
    context = parse_cycle_time(request.cycle).render_context()
    context.update(
        experiment_root=str(op.root), configuration_root=str(op.domain_file.parent)
    )
    path = Path(value.format(**context))
    return (
        path
        if path.is_absolute()
        else (op.root if output else op.domain_file.parent) / path
    )


def acquisition_plan(op, request):
    sources = op.section.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("acquisition.sources must be a nonempty list")
    result = []
    for item in sources:
        if request.source and item["name"] != request.source:
            continue
        context = parse_cycle_time(request.cycle).render_context()
        context.update(
            configuration_root=str(op.domain_file.parent), experiment_root=str(op.root)
        )
        source = item["source"].format(**context)
        if not source.startswith(("https://", "http://")):
            source = str(resolve(source, op, request))
        result.append(
            {
                "name": item["name"],
                "source": source,
                "destination": str(
                    resolve(item["destination"], op, request, output=True)
                ),
                "sha256": item.get("sha256"),
            }
        )
    if not result:
        raise ValueError(f"unknown acquisition source: {request.source}")
    destinations = [v["destination"] for v in result]
    if len(set(destinations)) != len(destinations):
        raise ValueError("acquisition sources must have distinct destinations")
    return result


def diagnostic_inputs(op, request):
    paths = []
    cost = op.section.get("cost_function")
    if cost:
        paths.append(resolve(cost["log"], op, request))
    for path in op.section.get("departures", {}).get("files", []):
        paths.append(resolve(path, op, request))
    if not paths:
        raise ValueError("diagnostics requires cost_function.log or departures.files")
    return paths


def diagnostics(op, request):
    root = resolve(
        op.section.get("run_dir", "diagnostics/{cycle_id}"), op, request, output=True
    )
    root.mkdir(parents=True, exist_ok=True)
    summary = {"cycle": request.cycle}
    cost = op.section.get("cost_function")
    if cost:
        text = resolve(cost["log"], op, request).read_text(errors="replace")
        pattern = cost.get("pattern", r"\bJ\s*=\s*([+\-0-9.eEdD]+)")
        values = [
            float(v.replace("D", "E").replace("d", "e"))
            for v in re.findall(pattern, text)
        ]
        import math

        if not values or not all(math.isfinite(v) for v in values):
            raise ValueError(
                "cost_function: no finite J values found; specify a capturing regex pattern for this log format"
            )
        summary["cost_function"] = {
            "values": values,
            "initial": values[0],
            "final": values[-1],
            "reduction_percent": (
                100 * (values[0] - values[-1]) / values[0] if values[0] else None
            ),
        }
        with (root / "cost_function.csv").open("w") as stream:
            writer = csv.writer(stream)
            writer.writerow(["index", "J"])
            writer.writerows(enumerate(values))
        # Plot exact numerical values; matplotlib is an optional plotting extra.
        if op.section.get("plots", False):
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots()
            ax.plot(range(len(values)), values, marker="o")
            ax.set(xlabel="Registro", ylabel="J", title=request.cycle)
            fig.tight_layout()
            fig.savefig(root / "cost_function.png")
            plt.close(fig)
    departures = op.section.get("departures")
    if departures:
        import numpy as np
        from netCDF4 import Dataset

        groups = departures.get("groups", {"background": "ombg", "analysis": "oman"})
        result = {}
        for filename in departures["files"]:
            path = resolve(filename, op, request)
            with Dataset(path) as dataset:
                for role, name in groups.items():
                    group = dataset
                    for segment in name.strip("/").split("/"):
                        if segment not in group.groups:
                            raise ValueError(f"{path}: missing departure group {name}")
                        group = group.groups[segment]
                    for variable, field in group.variables.items():
                        values = np.ma.asarray(field[:]).compressed()
                        values = values[np.isfinite(values)]
                        if not len(values):
                            continue
                        key = f"{role}/{variable}"
                        row = result.setdefault(
                            key,
                            {
                                "count": 0,
                                "sum": 0.0,
                                "sum_squares": 0.0,
                                "units": getattr(field, "units", "unknown"),
                            },
                        )
                        if row["units"] != getattr(field, "units", "unknown"):
                            raise ValueError(f"inconsistent units for {key}")
                        row["count"] += len(values)
                        row["sum"] += float(np.sum(values, dtype="float64"))
                        row["sum_squares"] += float(
                            np.sum(np.square(values.astype("float64")))
                        )
        if not result:
            raise ValueError("no finite departure observations found")
        summary["departures"] = {
            k: {
                "count": v["count"],
                "bias": v["sum"] / v["count"],
                "rmse": (v["sum_squares"] / v["count"]) ** 0.5,
                "units": v["units"],
            }
            for k, v in result.items()
        }
        summary["interpretation"] = (
            "Finite departures pooled per variable and group; no independent forecast-skill claim. QC selection must be configured upstream."
        )
    atomic_json(root / "summary.json", summary)
    return (
        [root / "summary.json"]
        + ([root / "cost_function.csv"] if cost else [])
        + (
            [root / "cost_function.png"]
            if cost and op.section.get("plots", False)
            else []
        )
    )


def product_operation(op, request, directory):
    plan = acquisition_plan(op, request) if op.key == "acquisition" else None
    inputs = (
        [
            Path(v["source"])
            for v in plan
            if not v["source"].startswith(("https://", "http://"))
        ]
        if plan
        else diagnostic_inputs(op, request)
    )
    state_path = directory / "state.json"
    state = json.loads(state_path.read_text()) if state_path.is_file() else None
    if request.action == "inspect":
        return {
            "state": "inspected",
            "configuration": op.section,
            "plan": plan,
            "inputs": list(map(str, inputs)),
            "identity": op.identity,
        }
    if request.action == "check":
        records(inputs)
        return {"state": "ready", "inputs": list(map(str, inputs))}
    if request.action == "status":
        return (
            {
                **state,
                "configuration_compatible": state["identity"] == op.identity,
                "current_identity": op.identity,
            }
            if state
            else {"state": "unprepared"}
        )
    if state and state["identity"] != op.identity:
        raise RuntimeError("configuration changed; use a new destination")
    if request.action != "prepare" and state is None:
        raise RuntimeError("operation is not prepared")
    runtime = (
        resolve(
            op.section.get("run_dir", "diagnostics/{cycle_id}"),
            op,
            request,
            output=True,
        )
        if op.key == "diagnostics"
        else None
    )
    guard = (
        ownership(runtime, directory, claim=request.action == "prepare")
        if runtime
        else nullcontext()
    )
    with lock(directory / "operation.lock"), guard:
        state = json.loads(state_path.read_text()) if state_path.is_file() else None
        if state and state["identity"] != op.identity:
            raise RuntimeError("configuration changed while acquiring lock")
        if request.action == "prepare":
            current = records(inputs)
            if state:
                if state["inputs"] != current:
                    raise RuntimeError("inputs changed; use a new destination")
                return {**state, "reused": True}
            state = {
                "identity": op.identity,
                "state": "prepared",
                "inputs": current,
                "plan": plan,
                "attempts": [],
                "acquired": {},
            }
            atomic_json(
                directory / "configuration.json",
                {"sources": op.sources, "configuration": op.section},
            )
        elif request.action == "run":
            if state["state"] == "running":
                raise RuntimeError(
                    "previous attempt is unfinished; inspect it before using a new destination"
                )
            if records(inputs) != state["inputs"]:
                raise RuntimeError("inputs changed after preparation")
            if state["state"] == "validated":
                if records([v["path"] for v in state["products"]]) != state["products"]:
                    raise RuntimeError("validated products changed")
                return {**state, "reused": True}
            state["attempts"].append({"started_at": now()})
            state["state"] = "running"
            atomic_json(state_path, state)
            try:
                if plan:
                    products = []
                    for item in plan:
                        target = Path(item["destination"])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if str(target) in state.get("acquired", {}):
                            if records([target])[0] != state["acquired"][str(target)]:
                                raise RuntimeError(
                                    f"acquired product changed: {target}"
                                )
                            products.append(target)
                            continue
                        if target.exists():
                            raise FileExistsError(
                                f"refusing to overwrite acquired product: {target}"
                            )
                        fd, name = tempfile.mkstemp(
                            dir=target.parent, prefix=".download-"
                        )
                        os.close(fd)
                        try:
                            if item["source"].startswith(("https://", "http://")):
                                with (
                                    urllib.request.urlopen(
                                        item["source"], timeout=120
                                    ) as source,
                                    open(name, "wb") as output,
                                ):
                                    expected = source.headers.get("Content-Length")
                                    shutil.copyfileobj(source, output)
                                if expected is not None and Path(
                                    name
                                ).stat().st_size != int(expected):
                                    raise ValueError(
                                        "incomplete acquisition transfer (Content-Length mismatch)"
                                    )
                            else:
                                shutil.copyfile(item["source"], name)
                            record = records([name])[0]
                            if item["sha256"] and record["sha256"] != item["sha256"]:
                                raise ValueError("acquisition checksum mismatch")
                            # Hard link publishes atomically and refuses overwrite.
                            os.link(name, target)
                        finally:
                            Path(name).unlink(missing_ok=True)
                        products.append(target)
                        state.setdefault("acquired", {})[str(target)] = records(
                            [target]
                        )[0]
                        atomic_json(state_path, state)
                else:
                    products = diagnostics(op, request)
                state["products"] = records(products)
                state["state"] = "finished"
            except Exception as error:
                state["state"] = "failed"
                state["attempts"][-1]["error"] = str(error)
                atomic_json(state_path, state)
                raise
            state["attempts"][-1]["finished_at"] = now()
        else:
            if records(inputs) != state["inputs"]:
                raise RuntimeError("inputs changed after execution")
            if state["state"] not in {"finished", "validated"}:
                raise RuntimeError("validate requires a completed run")
            if records([v["path"] for v in state["products"]]) != state["products"]:
                raise RuntimeError("products changed since execution")
            state["state"] = "validated"
            atomic_json(
                directory / "validation.json",
                {"valid": True, "products": state["products"], "identity": op.identity},
            )
        atomic_json(state_path, state)
        return state
