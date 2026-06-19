"""Read-only preflight checks for cyclic MONAN-JEDI experiments.

The doctor command reads a declarative YAML section and verifies filesystem
resources. It never creates files, directories or links, and it never renders,
executes or submits a workflow.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cycle_plan import load_cycle_plan_definition
from .timeline import (
    CycleInstance,
    TrajectoryState,
    format_mpas_timestamp,
    resolve_cycle_instances,
)
from .yaml_utils import load_yaml_file

VALID_KINDS = frozenset({"file", "directory", "executable"})
VALID_SCOPES = frozenset({"once", "cycle", "trajectory"})
VALID_ACCESS = frozenset({"read", "write", "execute"})
ACCESS_MODES = {
    "read": os.R_OK,
    "write": os.W_OK,
    "execute": os.X_OK,
}


class DoctorConfigError(ValueError):
    """Raised when the declarative doctor section is structurally invalid."""


@dataclass(frozen=True)
class DoctorCheck:
    """One declarative filesystem requirement."""

    name: str
    path: str
    kind: str
    scope: str = "once"
    access: tuple[str, ...] = ()


@dataclass(frozen=True)
class DoctorResult:
    """Outcome for one expanded doctor check."""

    check: DoctorCheck
    path: Path
    ok: bool
    detail: str


@dataclass(frozen=True)
class DoctorReport:
    """Read-only verification report and its process-style status."""

    results: tuple[DoctorResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)

    @property
    def passed(self) -> int:
        return sum(result.ok for result in self.results)

    @property
    def failed(self) -> int:
        return len(self.results) - self.passed


def _require_mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DoctorConfigError(f"{context} must be a YAML mapping")
    return value


def _parse_check(value: object, index: int) -> DoctorCheck:
    check = _require_mapping(value, f"doctor.checks[{index}]")
    name = check.get("name")
    path = check.get("path")
    kind = check.get("kind")
    scope = check.get("scope", "once")
    access = check.get("access", [])

    if not isinstance(name, str) or not name.strip():
        raise DoctorConfigError(
            f"doctor.checks[{index}].name must be a non-empty string"
        )
    if not isinstance(path, str) or not path.strip():
        raise DoctorConfigError(
            f"doctor.checks[{index}].path must be a non-empty string"
        )
    if kind not in VALID_KINDS:
        allowed = ", ".join(sorted(VALID_KINDS))
        raise DoctorConfigError(
            f"doctor.checks[{index}].kind must be one of: {allowed}"
        )
    if scope not in VALID_SCOPES:
        allowed = ", ".join(sorted(VALID_SCOPES))
        raise DoctorConfigError(
            f"doctor.checks[{index}].scope must be one of: {allowed}"
        )
    if not isinstance(access, list) or not all(isinstance(item, str) for item in access):
        raise DoctorConfigError(
            f"doctor.checks[{index}].access must be a YAML list of strings"
        )
    invalid_access = [item for item in access if item not in VALID_ACCESS]
    if invalid_access:
        allowed = ", ".join(sorted(VALID_ACCESS))
        raise DoctorConfigError(
            f"doctor.checks[{index}].access must contain only: {allowed}"
        )
    if len(set(access)) != len(access):
        raise DoctorConfigError(
            f"doctor.checks[{index}].access cannot contain duplicates"
        )

    return DoctorCheck(
        name=name,
        path=path,
        kind=kind,
        scope=scope,
        access=tuple(access),
    )


def load_doctor_checks(config_path: Path) -> list[DoctorCheck]:
    """Load and validate the ``doctor.checks`` declaration from a YAML file."""
    config = load_yaml_file(config_path)
    doctor = _require_mapping(config.get("doctor"), "Missing required mapping: doctor")
    checks = doctor.get("checks")
    if not isinstance(checks, list) or not checks:
        raise DoctorConfigError("doctor.checks must be a non-empty YAML list")
    return [_parse_check(value, index) for index, value in enumerate(checks)]


def _iso(value: object) -> str:
    return str(value).replace("+00:00", "Z")


def _hours(delta: object) -> int:
    return int(getattr(delta, "total_seconds")() // 3600)


def _cycle_context(instance: CycleInstance) -> dict[str, str]:
    return {
        "cycle_id": instance.cycle_id,
        "analysis_time": _iso(instance.analysis_time.isoformat()),
        "analysis_mpas_time": format_mpas_timestamp(instance.analysis_time),
        "forecast_start_time": _iso(instance.forecast_start_time.isoformat()),
        "forecast_start_mpas_time": format_mpas_timestamp(instance.forecast_start_time),
    }


def _trajectory_context(instance: CycleInstance, state: TrajectoryState) -> dict[str, str]:
    context = _cycle_context(instance)
    context.update(
        {
            "valid_time": _iso(state.valid_time.isoformat()),
            "valid_mpas_time": state.mpas_file_date,
            "offset_hours": str(_hours(state.offset_from_analysis)),
            "forecast_lead_hours": str(_hours(state.forecast_lead)),
        }
    )
    return context


def _format_path(template: str, context: Mapping[str, str], check_name: str) -> str:
    try:
        return template.format_map(context)
    except KeyError as exc:
        raise DoctorConfigError(
            f"doctor check {check_name!r} uses unknown placeholder: {exc.args[0]}"
        ) from exc
    except ValueError as exc:
        raise DoctorConfigError(
            f"doctor check {check_name!r} has an invalid path template: {template!r}"
        ) from exc


def _path_from_template(template: str, config_path: Path) -> Path:
    candidate = Path(template).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve(strict=False)


def _expanded_checks(
    config_path: Path,
    checks: list[DoctorCheck],
) -> list[tuple[DoctorCheck, Path]]:
    expanded: list[tuple[DoctorCheck, Path]] = []
    instances: list[CycleInstance] | None = None

    for check in checks:
        if check.scope == "once":
            resolved = _format_path(check.path, {}, check.name)
            expanded.append((check, _path_from_template(resolved, config_path)))
            continue

        if instances is None:
            instances = resolve_cycle_instances(load_cycle_plan_definition(config_path))

        for instance in instances:
            if check.scope == "cycle":
                resolved = _format_path(check.path, _cycle_context(instance), check.name)
                expanded.append((check, _path_from_template(resolved, config_path)))
                continue

            for state in instance.trajectory:
                resolved = _format_path(
                    check.path,
                    _trajectory_context(instance, state),
                    check.name,
                )
                expanded.append((check, _path_from_template(resolved, config_path)))

    return expanded


def _check_access(check: DoctorCheck, path: Path, base_detail: str) -> DoctorResult:
    for access in check.access:
        if not os.access(path, ACCESS_MODES[access]):
            return DoctorResult(check, path, False, f"missing {access} access")
    if check.access:
        base_detail = f"{base_detail}; {', '.join(check.access)} access"
    return DoctorResult(check, path, True, base_detail)


def _evaluate(check: DoctorCheck, path: Path) -> DoctorResult:
    if check.kind == "file":
        if path.is_file():
            return _check_access(check, path, "regular file")
        detail = "missing" if not path.exists() else "not a regular file"
        return DoctorResult(check, path, False, detail)

    if check.kind == "directory":
        if path.is_dir():
            return _check_access(check, path, "directory")
        detail = "missing" if not path.exists() else "not a directory"
        return DoctorResult(check, path, False, detail)

    if path.is_file() and os.access(path, os.X_OK):
        return _check_access(check, path, "executable file")
    if not path.exists():
        detail = "missing"
    elif not path.is_file():
        detail = "not a regular file"
    else:
        detail = "not executable"
    return DoctorResult(check, path, False, detail)


def run_doctor(config_path: Path) -> DoctorReport:
    """Run every configured check without writing to the filesystem."""
    checks = load_doctor_checks(config_path)
    results = tuple(
        _evaluate(check, path) for check, path in _expanded_checks(config_path, checks)
    )
    return DoctorReport(results=results)


def format_doctor_report(report: DoctorReport) -> str:
    """Render a stable human-readable report for the doctor command."""
    lines = [
        "doctor: read-only verification",
        "doctor: no files, directories, links, rendered runtime, or jobs will be created",
        "",
    ]
    for result in report.results:
        status = "OK" if result.ok else "FAIL"
        lines.append(
            f"[{status}] {result.check.name} [{result.check.kind}] "
            f"{result.path} ({result.detail})"
        )
    lines.extend(["", f"summary: {report.passed} passed, {report.failed} failed"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the standalone read-only doctor command."""
    parser = argparse.ArgumentParser(
        prog="monan-jedi-cycle-doctor",
        description="Verify declared cyclic MONAN-JEDI resources without side effects.",
    )
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args(argv)
    report = run_doctor(args.experiment)
    print(format_doctor_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
