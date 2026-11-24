"""Read-only operational and variational evidence for JEDI campaigns.

Adapted from the historical M3 generate_campaign_figures.py method. No PBS
submission; unverifiable cycles and unparseable minimizations are reported,
never presented as scientific successes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?"
_QUADRATIC = re.compile(r"Quadratic cost function:\s*J\s*\(\s*(\d+)\s*\)\s*=\s*(" + _NUMBER + r")")
_NONLINEAR = re.compile(r"CostFunction:\s*Nonlinear J\s*=\s*(" + _NUMBER + r")")


def parse_cost(text: str) -> list[tuple[int, float]]:
    """Parse one outer-loop quadratic total J, not Jb or JoJc.

    Following historical M3, a nonlinear J may supply iteration zero if the
    log starts the quadratic sequence at iteration one. Multiple outer loops
    are rejected rather than accidentally mixing their costs.
    """
    values: list[tuple[int, float]] = []
    initial = None
    for line in text.splitlines():
        start = _NONLINEAR.search(line)
        if start and not values:
            initial = float(start[1].replace("D", "e").replace("d", "e"))
        found = _QUADRATIC.search(line)
        if not found:
            continue
        iteration = int(found[1])
        value = float(found[2].replace("D", "e").replace("d", "e"))
        if values and iteration <= values[-1][0]:
            raise ValueError("repeated or multiple outer minimizations in JEDI log")
        values.append((iteration, value))
    if not values or (values[0][0] != 0 and initial is None):
        raise ValueError("initial cost or quadratic iterations not found")
    if values[0][0] != 0:
        values.insert(0, (0, initial))
    if values[0][1] <= 0 or any(not np.isfinite(v) or v < 0 for _, v in values):
        raise ValueError("nonfinite, negative or zero-initial J")
    return values


def _manifest(root: Path, cycle: str, stage: str) -> tuple[dict | None, str | None]:
    path = root / "work" / stage / cycle / ".monan-jedi-workflow" / f"{stage}-validation.json"
    if not path.is_file():
        return None, f"missing validation manifest: {path}"
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return None, f"unreadable manifest {path}: {error}"
    if doc.get("valid") is not True or doc.get("cycle_id") != cycle:
        return None, f"invalid or wrong-cycle validation manifest: {path}"
    return doc, None


def _workflow_state(root: Path) -> dict:
    """Read task status from SQLite without relying on historical cycle_id."""
    path = root / ".simpleworkflow" / "state.sqlite3"
    if not path.is_file():
        return {"available": False, "reason": "SQLite state missing"}
    try:
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
            fields = {r[1] for r in db.execute("PRAGMA table_info(task_state)")}
            if not {"task", "status"}.issubset(fields):
                return {"available": False, "reason": "task_state lacks task/status"}
            rows = db.execute("SELECT task, status FROM task_state").fetchall()
    except (OSError, sqlite3.Error) as error:
        return {"available": False, "reason": str(error)}
    return {"available": True, "tasks_total": len(rows),
            "tasks_success": sum(str(s).lower() == "success" for _, s in rows),
            "non_success": [{"task": name, "status": status} for name, status in rows
                            if str(status).lower() != "success"][:25]}


def collect_evidence(root: Path, cycles: list[str]) -> dict:
    """Inspect JEDI/MPAS manifests and JEDI logs for expected campaign cycles."""
    root = root.expanduser().resolve()
    state = _workflow_state(root)
    continuity, convergence, iterations, gaps = [], [], [], []
    for i, cycle in enumerate(cycles):
        jedi, error = _manifest(root, cycle, "jedi")
        mpas, mpas_error = _manifest(root, cycle, "mpas") if i < len(cycles) - 1 else (None, None)
        problems = []
        if error:
            problems.append(error)
        if mpas_error:
            problems.append(mpas_error)
        # Success requires validated science products, not only presence of a folder.
        valid = not problems
        continuity.append({"cycle": cycle, "jedi_valid": jedi is not None,
                           "mpas_valid": mpas is not None if i < len(cycles)-1 else None,
                           "validated": valid})
        gaps.extend({"cycle": cycle, "kind": "continuity", "detail": p} for p in problems)
        if jedi is None:
            continue
        rawlog = jedi.get("log")
        if not isinstance(rawlog, str) or not rawlog:
            gaps.append({"cycle": cycle, "kind": "cost", "detail": "JEDI validation lacks log"})
            continue
        log = Path(rawlog)
        if not log.is_absolute():
            log = root / "work" / "jedi" / cycle / log
        # Never read a log outside the selected experiment.
        try:
            log = log.resolve(strict=True)
            log.relative_to(root)
            raw = log.read_text(errors="replace")
            if "OOPS Ending" not in raw:
                raise ValueError("OOPS Ending marker missing")
            curve = parse_cost(raw)
        except (OSError, ValueError) as ex:
            gaps.append({"cycle": cycle, "kind": "cost", "detail": str(ex)})
            continue
        start, end = curve[0][1], curve[-1][1]
        monotonic = all(right <= left for (_, left), (_, right) in zip(curve, curve[1:]))
        convergence.append({"cycle": cycle, "iterations": curve[-1][0],
                            "J_initial": start, "J_final": end,
                            "reduction_percent": 100 * (1 - end/start),
                            "monotonic": monotonic, "log": str(log),
                            "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
        iterations.extend({"cycle": cycle, "iteration": it, "J": cost,
                           "J_normalized": cost/start} for it, cost in curve)
    complete = bool(state["available"] and state["tasks_total"] and
                    state["tasks_total"] == state["tasks_success"] and
                    len(continuity) == len(cycles) and
                    all(row["validated"] for row in continuity))
    return {"cycles_expected": len(cycles), "continuity": continuity,
            "convergence": convergence, "cost_iterations": iterations,
            "workflow": state, "campaign_complete": complete,
            "gaps": gaps, "method": "historical M3 quadratic J, single outer loop; normalized J/J0"}


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_evidence(evidence: dict, output: Path) -> list[str]:
    """Write evidence tables and validated figures alongside existing plots."""
    output.mkdir(parents=True, exist_ok=True)
    _csv(output / "campaign_completion.csv",
         ["cycle", "jedi_valid", "mpas_valid", "validated"], evidence["continuity"])
    _csv(output / "jedi_convergence.csv",
         ["cycle", "iterations", "J_initial", "J_final", "reduction_percent",
          "monotonic", "log", "log_sha256"], evidence["convergence"])
    _csv(output / "jedi_cost_iterations.csv",
         ["cycle", "iteration", "J", "J_normalized"], evidence["cost_iterations"])
    names: list[str] = []
    if evidence["campaign_complete"]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(12, 3.2))
        dates = [datetime.strptime(r["cycle"], "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc) for r in evidence["continuity"]]
        ax.plot(dates, [1]*len(dates), color="#18864b", lw=1.6)
        ax.scatter(dates, [1]*len(dates), color="#18864b", s=65, zorder=3)
        ax.set_yticks([1], labels=["Validado"])
        ax.set_ylim(.65, 1.35)
        ax.grid(axis="x", alpha=.2)
        ax.set_title(f"Continuidade da campanha — {len(dates)} ciclos validados")
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(output / "campaign_completion.png", dpi=170)
        plt.close(fig)
        names.append("campaign_completion.png")
    if evidence["convergence"]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import Normalize
        from matplotlib.cm import ScalarMappable
        by_cycle: dict[str, list[dict]] = {}
        for record in evidence["cost_iterations"]:
            by_cycle.setdefault(record["cycle"], []).append(record)
        names_order = sorted(by_cycle)
        fig, ax = plt.subplots(figsize=(11, 6))
        norm = Normalize(vmin=0, vmax=max(1, len(names_order)-1))
        for i, cycle in enumerate(names_order):
            rows = sorted(by_cycle[cycle], key=lambda r: r["iteration"])
            ax.plot([r["iteration"] for r in rows], [r["J_normalized"] for r in rows],
                    color=plt.cm.viridis(norm(i)), alpha=.8, linewidth=1.2)
        ax.axhline(1, ls="--", color="gray", linewidth=.8)
        ax.set(xlabel="Iteração DRPCG", ylabel="J/J₀",
               title=f"Convergência da função custo — {len(names_order)}/{evidence['cycles_expected']} ciclos")
        ax.grid(alpha=.2)
        fig.colorbar(ScalarMappable(norm=norm, cmap="viridis"), ax=ax,
                     label="Índice cronológico do ciclo")
        fig.tight_layout()
        fig.savefig(output / "jedi_cost_convergence.png", dpi=170)
        plt.close(fig)
        names.append("jedi_cost_convergence.png")
    return names
