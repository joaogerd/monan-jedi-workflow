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
    from .plot_style import GREEN, INK, GRID, MUTED, dates, heading, save, style, time_axis
    names: list[str] = []
    with style() as plt:
        if evidence["campaign_complete"]:
            import matplotlib.dates as mdates
            from datetime import timedelta
            fig, ax = plt.subplots(figsize=(12.2, 3.8))
            fig.subplots_adjust(left=.045, right=.985, bottom=.23, top=.78)
            cycles = [r["cycle"] for r in evidence["continuity"]]
            times = dates(cycles)
            count = len(times)
            workflow = evidence["workflow"]
            completed = workflow["tasks_success"]
            total = workflow["tasks_total"]
            duration = (times[-1] - times[0]).total_seconds()/3600
            heading(fig, "Continuidade da campanha MONAN-JEDI 3DVar/FGAT",
                    f"{duration:g} horas • {count}/{count} ciclos validados"
                    f" • {completed}/{total} tarefas concluídas", left=.045)
            day = times[0].replace(hour=0, minute=0, second=0, microsecond=0)
            end_day = times[-1]
            number = 0
            while day <= end_day:
                if number % 2 == 0:
                    ax.axvspan(day, day+timedelta(days=1), color="#f3f4f6",
                               alpha=.85, zorder=0)
                label_time = min(day+timedelta(hours=12), end_day)
                ax.text(label_time, .35, day.strftime("%d/%m"),
                        ha="center", color=MUTED, fontsize=9)
                day += timedelta(days=1)
                number += 1
            ax.plot(times, [0]*count, color="#9ca3af", lw=1.8)
            ax.scatter(times, [0]*count, s=190, color=GREEN,
                       edgecolor="white", linewidth=1.8, zorder=3)
            for date in times:
                ax.text(date, 0, "✓", ha="center", va="center",
                        fontsize=10, weight="bold", color="white", zorder=4)
            ax.set_ylim(-.47, .56)
            ax.set_yticks([])
            ax.spines["left"].set_visible(False)
            ax.spines["bottom"].set_color(GRID)
            time_axis(ax, times, max_ticks=15)
            save(fig, output, "campaign_completion")
            plt.close(fig)
            names.append("campaign_completion.png")
        if evidence["convergence"]:
            import numpy as np
            from matplotlib.colors import Normalize
            from matplotlib.cm import ScalarMappable
            by_cycle: dict[str, list[dict]] = {}
            for record in evidence["cost_iterations"]:
                by_cycle.setdefault(record["cycle"], []).append(record)
            ordered_cycles = sorted(by_cycle)
            fig, ax = plt.subplots(figsize=(12.2, 6.6))
            fig.subplots_adjust(left=.09, right=.97, bottom=.13, top=.83)
            norm = Normalize(vmin=0, vmax=max(1, len(ordered_cycles)-1))
            steps = sorted({r["iteration"] for r in evidence["cost_iterations"]})
            curves = np.full((len(ordered_cycles), len(steps)), np.nan)
            reductions = [r["reduction_percent"] for r in evidence["convergence"]]
            monotonic = sum(bool(r["monotonic"]) for r in evidence["convergence"])
            heading(fig, "Convergência da função custo",
                    f"{len(ordered_cycles)}/{evidence['cycles_expected']} ciclos com J disponível"
                    f" • redução média = {float(np.mean(reductions)):.1f}%"
                    f" • monotônica em {monotonic}/{len(ordered_cycles)} ciclos",
                    left=.09)
            for index, cycle in enumerate(ordered_cycles):
                rows = sorted(by_cycle[cycle], key=lambda r: r["iteration"])
                x = [r["iteration"] for r in rows]
                y = [r["J_normalized"] for r in rows]
                ax.plot(x, y, color=plt.cm.viridis(norm(index)),
                        marker="o", ms=2.6, lw=1.5, alpha=.84)
                for row in rows:
                    curves[index, steps.index(row["iteration"])] = row["J_normalized"]
            ax.plot(steps, np.nanmedian(curves, axis=0), color=INK, lw=3,
                    label="Mediana dos ciclos", zorder=4)
            ax.axhline(1, color="#9ca3af", ls="--", lw=1)
            ax.set_xlabel("Iteração do minimizador DRPCG")
            ax.set_ylabel("Função custo normalizada  J/J₀")
            ax.set_xticks(steps)
            ax.grid(axis="y", color=GRID, alpha=.65, lw=.8)
            ax.legend(loc="lower left", frameon=False)
            colorbar = fig.colorbar(ScalarMappable(norm=norm, cmap="viridis"),
                                   ax=ax, fraction=.045, pad=.03)
            ids = np.unique(np.linspace(0, len(ordered_cycles)-1,
                                        min(6, len(ordered_cycles))).astype(int))
            colorbar.set_ticks(ids)
            colorbar.set_ticklabels([
                dates([ordered_cycles[i]])[0].strftime("%d/%m %HZ") for i in ids
            ])
            colorbar.set_label("Ciclo da campanha")
            colorbar.outline.set_visible(False)
            save(fig, output, "jedi_cost_convergence")
            plt.close(fig)
            names.append("jedi_cost_convergence.png")
    return names
