"""Read-only preflight for an orchestrated MONAN-JEDI analysis cycle.

``cycle-doctor`` is intentionally not an orchestrator and not a replacement for
stage-specific validation.  It answers a smaller question before expensive
work begins: are the declared stage contracts present and can the JEDI cycle be
resolved for the requested analysis time?

The command never creates a runtime, runs a converter, calls MPI or submits a
PBS job.  This property makes it safe to use from documentation, CI and future
operational adapters.

Deep checks remain owned by the relevant domain stage.  For example,
``obs2ioda-doctor`` knows how to probe converter executables and observation
inputs; duplicating those rules here would couple unrelated components.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .jedi_stage import load_jedi_run


@dataclass(frozen=True)
class DoctorCheck:
    """One human- and machine-readable preflight result."""

    name: str
    ok: bool
    detail: str


def _check_file(config_dir: Path, name: str, *, required: bool) -> DoctorCheck:
    """Check whether one stage configuration file exists without opening it."""
    path = config_dir / name
    if path.is_file():
        return DoctorCheck(name=name, ok=True, detail=str(path))
    if required:
        return DoctorCheck(name=name, ok=False, detail=f"missing: {path}")
    return DoctorCheck(name=name, ok=True, detail="optional and not configured")


def doctor_cycle(
    config_dir: Path,
    cycle_time: str,
    *,
    require_observations: bool = True,
    require_forecast: bool = True,
) -> dict[str, Any]:
    """Build a side-effect-free preflight report for one analysis time.

    Parameters
    ----------
    config_dir
        Case directory containing stage YAML files.
    cycle_time
        Analysis time in ISO-8601 form.
    require_observations
        Whether ``obs2ioda.yaml`` is a blocking requirement.
    require_forecast
        Whether ``mpas.yaml`` is a blocking requirement.

    Returns
    -------
    dict
        JSON-serializable report.  ``ready`` reflects blocking domain
        contracts only.  The absence of simpleWorkflow is reported but does
        not make domain stages unusable, so it is not a blocking error.

    Notes
    -----
    This function deliberately calls ``load_jedi_run`` rather than
    ``prepare_jedi``.  A doctor must be safe to run repeatedly and must never
    mutate a scientific runtime merely to check configuration.
    """
    config_dir = config_dir.resolve()
    checks: list[DoctorCheck] = [
        _check_file(config_dir, "jedi.yaml", required=True),
        _check_file(
            config_dir, "obs2ioda.yaml", required=require_observations
        ),
        _check_file(config_dir, "mpas.yaml", required=require_forecast),
    ]

    try:
        run = load_jedi_run(config_dir, cycle_time)
        checks.append(
            DoctorCheck(
                name="jedi-contract",
                ok=True,
                detail=(
                    f"run_dir={run.run_dir}; "
                    f"first_cycle={str(run.is_first_cycle).lower()}"
                ),
            )
        )
    except Exception as error:  # noqa: BLE001 - doctor must report config errors.
        checks.append(
            DoctorCheck(
                name="jedi-contract",
                ok=False,
                detail=f"{type(error).__name__}: {error}",
            )
        )

    # simpleWorkflow is intentionally optional at the domain layer.  Reporting
    # its presence is still useful because the reference research tutorial uses
    # `swf`, while ecFlow/Cylc adapters may call the same stages instead.
    simpleworkflow = shutil.which("swf") or shutil.which("simpleworkflow")
    checks.append(
        DoctorCheck(
            name="simpleWorkflow",
            ok=bool(simpleworkflow),
            detail=(
                simpleworkflow
                or "not found in PATH; domain stages remain usable directly"
            ),
        )
    )

    blocking_names = {"jedi.yaml", "jedi-contract"}
    if require_observations:
        blocking_names.add("obs2ioda.yaml")
    if require_forecast:
        blocking_names.add("mpas.yaml")

    blocking_failures = [
        check for check in checks if not check.ok and check.name in blocking_names
    ]
    return {
        "schema_version": 1,
        "cycle_time": cycle_time,
        "config_dir": str(config_dir),
        "ready": not blocking_failures,
        "checks": [asdict(check) for check in checks],
    }


def print_doctor_report(
    report: dict[str, Any], *, json_output: bool = False
) -> None:
    """Print a compact user report or the exact JSON representation."""
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    for check in report["checks"]:
        if check["ok"]:
            marker = "OK"
        elif check["name"] == "simpleWorkflow":
            marker = "WARN"
        else:
            marker = "ERROR"
        print(f"[{marker}] {check['name']}: {check['detail']}")

    state = "ready" if report["ready"] else "not ready"
    marker = "OK" if report["ready"] else "ERROR"
    print(f"[{marker}] cycle contract {state}: {report['cycle_time']}")
