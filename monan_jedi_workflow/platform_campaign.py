"""Pure campaign description and simpleWorkflow export; never execute tasks."""

from dataclasses import replace
from pathlib import Path
import re
import yaml
from .domain_cli import _utc_cycle
from .platform_config import read_yaml, reference, load_operation

OPERATIONS = {
    "obs.acquire": ("obs", "acquire"),
    "obs.convert": ("obs", "convert"),
    "jedi": ("jedi", "assimilation"),
    "mpas": ("mpas", "forecast"),
    "mpas.init": ("mpas", "init"),
    "diagnostics": ("diagnostics", "diagnostics"),
}


def operation_tasks(request, principal, operation, cycle, prefix, previous):
    """Translate a single domain lifecycle to motor tasks, without executing it."""
    if operation not in OPERATIONS:
        raise ValueError(f"unsupported campaign operation: {operation}")
    app, domain = OPERATIONS[operation]
    op = load_operation(
        replace(request, app=app, operation=domain, config=principal, cycle=cycle)
    )
    command = [app] + (
        [domain] if operation in {"obs.acquire", "obs.convert", "mpas.init"} else []
    )
    tasks = []
    for action in ("prepare", "run", "validate"):
        name = f'{prefix}_{operation.replace(".", "_")}_{action}'
        task = {
            "name": name,
            "argv": [*command, action, str(principal), "--cycle", cycle],
            "executor": "local",
        }
        if previous:
            task["depends_on"] = [previous]
        required = list(op.sources)
        required += [
            v["source"]
            for v in op.section.get("templates", [])
            if Path(v["source"]).is_file()
        ]
        task["inputs"] = {"required": required}
        task["input_fingerprint"] = "sha256"
        if (
            action == "run"
            and op.site.get("execution", {}).get("mode", "pbs") == "pbs"
            and app in {"jedi", "mpas"}
        ):
            pbs = op.section.get("pbs", {})
            task["executor"] = "pbs"
            task["pbs"] = {
                k: pbs[k]
                for k in ("queue", "walltime", "select", "ncpus", "mpiprocs")
                if k in pbs
            }
            task["pbs"]["inherit_environment"] = True
        tasks.append(task)
        previous = name
    return tasks


def campaign_action(request):
    if request.engine not in {None, "simpleworkflow"}:
        raise ValueError("beta supports only simpleworkflow export")
    path = request.config.resolve()
    config = read_yaml(path)
    if config.get("schema_version") != 1:
        raise ValueError("campaign schema_version must be 1")
    principal = reference(config["experiment"], path.parent)
    calendar = config["calendar"]
    start = _utc_cycle(calendar["start"])
    end = _utc_cycle(calendar["end"])
    match = re.fullmatch(r"PT([1-9][0-9]*)H", calendar["interval"])
    if not match:
        raise ValueError("calendar.interval must be a positive integer-hour duration")
    from .corrected_campaign import _cycles, _iso

    cycles = _cycles(start, end, int(match[1]))
    inclusive = calendar.get("end_inclusive", True)
    if not isinstance(inclusive, bool):
        raise ValueError("calendar.end_inclusive must be boolean")
    if not inclusive:
        cycles = cycles[:-1]
    if not cycles:
        raise ValueError("campaign calendar is empty")
    forecast_last = config.get("last_cycle", {}).get("forecast", True)
    if not isinstance(forecast_last, bool):
        raise ValueError("last_cycle.forecast must be boolean")
    selected = config.get(
        "operations", ["obs.acquire", "obs.convert", "jedi", "mpas", "diagnostics"]
    )
    if (
        not isinstance(selected, list)
        or not selected
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("operations must be a nonempty list without duplicates")
    if "mpas.init" in selected:
        raise ValueError(
            "put mpas.init in initialization, not in the repeating cycle operations"
        )
    if any(value not in OPERATIONS for value in selected):
        raise ValueError("unsupported campaign operation")
    for before, after in (
        ("obs.acquire", "obs.convert"),
        ("obs.convert", "jedi"),
        ("jedi", "mpas"),
        ("jedi", "diagnostics"),
    ):
        if (
            before in selected
            and after in selected
            and selected.index(before) > selected.index(after)
        ):
            raise ValueError(f"{before} must precede {after}")
    declared_interval = read_yaml(principal).get("cycle", {}).get("interval")
    if declared_interval is not None and declared_interval != calendar["interval"]:
        raise ValueError("campaign interval differs from experiment cycle.interval")
    initial = config.get("initialization", [])
    if not isinstance(initial, list):
        raise ValueError(
            "initialization must be an ordered list of operation/cycle entries"
        )
    initialization_tasks = []
    previous = None
    for index, item in enumerate(initial):
        own_principal = reference(item.get("experiment", str(principal)), path.parent)
        own_cycle = _utc_cycle(item["cycle"])
        tasks = operation_tasks(
            request,
            own_principal,
            item["operation"],
            own_cycle,
            f"init{index:03d}",
            previous,
        )
        initialization_tasks.extend(tasks)
        previous = tasks[-1]["name"]
    tasks = []
    previous = None
    for index, cycle in enumerate(cycles):
        for operation in selected:
            if operation == "mpas" and index == len(cycles) - 1 and not forecast_last:
                continue
            generated = operation_tasks(
                request, principal, operation, _iso(cycle), f"c{index:05d}", previous
            )
            tasks.extend(generated)
            previous = generated[-1]["name"]
    document = {
        "format_version": 1,
        "workflow": {"name": config.get("name", "monan_jedi_beta")},
        "tasks": tasks,
    }
    if initialization_tasks:
        document["initialization"] = {"tasks": initialization_tasks}
    report = {
        "state": "checked" if request.action == "check" else "inspected",
        "cycles": len(cycles),
        "tasks": len(tasks),
        "initialization_tasks": len(initialization_tasks),
        "first_cycle": _iso(cycles[0]),
        "last_cycle": _iso(cycles[-1]),
        "operations": selected,
    }
    if request.action == "export":
        output = reference(config.get("output", "workflow.yaml"), path.parent)
        if output.exists():
            raise FileExistsError(f"workflow exists; choose a new output: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x") as stream:
            yaml.safe_dump(document, stream, sort_keys=False)
        report.update(state="exported", workflow=str(output))
    return report
