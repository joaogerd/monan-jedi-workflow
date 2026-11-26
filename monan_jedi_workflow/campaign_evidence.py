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

_COMPONENT = re.compile(r"Quadratic cost function:\s*(Jb|JoJc)\s*\(\s*(\d+)\s*\)\s*=\s*(" + _NUMBER + r")")
_RESIDUAL = re.compile(r"(?:norm(?:a)?\s+(?:of\s+)?(?:the\s+)?residual|residual\s+norm)\s*(?:\(\s*(\d+)\s*\))?\s*[:=]\s*(" + _NUMBER + r")", re.I)


def parse_cost_components(text: str, curve: list[tuple[int, float]]) -> list[dict]:
    """Return only explicitly logged Jb, JoJc and iteration-indexed residual.

    Never derive missing components as J - other component; the nonlinear J0
    and inner quadratic components are not necessarily directly comparable.
    Ambiguous or repeated component iterations are excluded.
    """
    valid = {i for i, _ in curve}
    components: dict[tuple[int, str], float] = {}
    duplicated: set[tuple[int, str]] = set()
    for line in text.splitlines():
        found = _COMPONENT.search(line)
        if not found:
            continue
        label, iteration = found[1], int(found[2])
        key = (iteration, label)
        value = float(found[3].replace("D", "e").replace("d", "e"))
        if key in components:
            duplicated.add(key)
        elif np.isfinite(value) and iteration in valid:
            components[key] = value
    for key in duplicated:
        components.pop(key, None)
    records: list[dict] = []
    for iteration, j in curve:
        record = {"iteration": iteration, "J": j,
                  "Jb": components.get((iteration, "Jb")),
                  "JoJc": components.get((iteration, "JoJc"))}
        records.append(record)
    # The residual is not inferred without a known per-iteration key.
    residual: dict[int, float] = {}
    duplicate_residual: set[int] = set()
    for line in text.splitlines():
        found = _RESIDUAL.search(line)
        if found is None or found[1] is None:
            continue
        it = int(found[1])
        value = float(found[2].replace("D", "e").replace("d", "e"))
        if it in residual:
            duplicate_residual.add(it)
        elif it in valid and np.isfinite(value) and value >= 0:
            residual[it] = value
    for it in duplicate_residual:
        residual.pop(it, None)
    for record in records:
        record["residual_norm"] = residual.get(record["iteration"])
    return records



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
    continuity, convergence, iterations, components, gaps = [], [], [], [], []
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
        components.extend({"cycle": cycle, **record} for record in parse_cost_components(raw, curve))
    complete = bool(state["available"] and state["tasks_total"] and
                    state["tasks_total"] == state["tasks_success"] and
                    len(continuity) == len(cycles) and
                    all(row["validated"] for row in continuity))
    return {"cycles_expected": len(cycles), "continuity": continuity,
            "convergence": convergence, "cost_iterations": iterations,
            "cost_components": components,
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
    _csv(output / "jedi_cost_components.csv",
         ["cycle", "iteration", "J", "Jb", "JoJc", "residual_norm"],
         evidence.get("cost_components", []))
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
            from .plot_style import BLUE, TEAL
            by_cycle: dict[str, list[dict]] = {}
            for record in evidence["cost_iterations"]:
                by_cycle.setdefault(record["cycle"], []).append(record)
            ordered_cycles = sorted(by_cycle)
            steps = sorted({r["iteration"] for r in evidence["cost_iterations"]})
            curves = np.full((len(ordered_cycles), len(steps)), np.nan)
            reductions = [r["reduction_percent"] for r in evidence["convergence"]]
            monotonic = sum(bool(r["monotonic"]) for r in evidence["convergence"])

            fig, ax = plt.subplots(figsize=(12.2, 6.2))
            fig.subplots_adjust(left=.09, right=.975, bottom=.14, top=.80)
            heading(fig, "Convergência da função custo",
                    f"{len(ordered_cycles)}/{evidence['cycles_expected']} ciclos com J disponível"
                    f" • redução média = {float(np.mean(reductions)):.1f}%"
                    f" • redução monotônica em {monotonic}/{len(ordered_cycles)} ciclos",
                    left=.09)
            for index, cycle in enumerate(ordered_cycles):
                rows = sorted(by_cycle[cycle], key=lambda r: r["iteration"])
                x = [r["iteration"] for r in rows]
                y = [r["J_normalized"] for r in rows]
                ax.plot(x, y, color=BLUE, lw=1.0, alpha=.18, zorder=1)
                for row in rows:
                    curves[index, steps.index(row["iteration"])] = row["J_normalized"]
            # The median is a per-iteration, across-cycle statistic; the
            # interquartile envelope represents cross-cycle variability,
            # not uncertainty bounds or confidence intervals.
            median = np.nanmedian(curves, axis=0)
            q25 = np.nanpercentile(curves, 25, axis=0)
            q75 = np.nanpercentile(curves, 75, axis=0)
            ax.fill_between(steps, q25, q75, color=TEAL, alpha=.13,
                            label="Intervalo interquartil (ciclos)", zorder=2)
            ax.plot(steps, median, color=TEAL, lw=2.7, marker="o",
                    ms=6, mfc="white", mew=1.6,
                    label="Mediana de J/J₀", zorder=4)
            ax.axhline(1, color=MUTED, ls="--", lw=1, alpha=.6)
            ax.set_xlabel("Iteração do minimizador DRPCG")
            ax.set_ylabel("Função custo normalizada  J/J₀")
            ax.set_xticks(steps)
            ax.grid(axis="y", color=GRID, alpha=.65, lw=.8)
            ax.legend(loc="upper right", frameon=False)
            ax.text(.015, .045,
                    f"Redução média de J\n{float(np.mean(reductions)):.1f}%"
                    f"\nCiclos: {len(ordered_cycles)}",
                    transform=ax.transAxes, va="bottom", color=MUTED,
                    bbox={"boxstyle": "round,pad=.45", "facecolor": "white",
                          "edgecolor": GRID, "alpha": .95})
            save(fig, output, "jedi_cost_convergence")
            plt.close(fig)
            names.append("jedi_cost_convergence.png")

            # Separate detail figure, never imputing Jb/JoJc/residual. Pick
            # first cycle with BOTH logged components, deterministic by time.
            rows_by_cycle: dict[str, list[dict]] = {}
            for item in evidence.get("cost_components", []):
                rows_by_cycle.setdefault(item["cycle"], []).append(item)
            detailed = next(
                (cycle for cycle in sorted(rows_by_cycle)
                 if any(row["Jb"] is not None and row["JoJc"] is not None
                        for row in rows_by_cycle[cycle])), None)
            if detailed is not None:
                detail = sorted(rows_by_cycle[detailed], key=lambda row: row["iteration"])
                fig, ax = plt.subplots(figsize=(12.2, 6.2))
                fig.subplots_adjust(left=.09, right=.975, bottom=.14, top=.80)
                detail_reduction = next(r["reduction_percent"]
                                        for r in evidence["convergence"]
                                        if r["cycle"] == detailed)
                heading(fig, "Função custo — decomposição por iteração",
                        f"Ciclo {dates([detailed])[0]:%d/%m/%Y %HZ}"
                        f" • redução de J = {detail_reduction:.1f}%"
                        f" • componentes extraídas do log JEDI", left=.09)
                x = [r["iteration"] for r in detail]
                for key, label, color, line in (
                        ("J", "J — total", BLUE, "-"),
                        ("Jb", "Jb — background", "#d97706", "--"),
                        ("JoJc", "Jo + Jc — observações e restrições", TEAL, "-.")):
                    points = [(r["iteration"], r[key]) for r in detail
                              if r[key] is not None]
                    if not points:
                        continue
                    ax.plot([p[0] for p in points], [p[1] for p in points],
                            color=color, ls=line, lw=2.3, marker="o", ms=5,
                            mfc="white", mew=1.5, label=label)
                residuals = [(r["iteration"], r["residual_norm"]) for r in detail
                             if r["residual_norm"] is not None]
                if len(residuals) > 1:
                    ax2 = ax.twinx()
                    ax2.plot([p[0] for p in residuals], [p[1] for p in residuals],
                             color="#b45385", ls=":", lw=2,
                             marker="D", ms=4, label="Norma do resíduo")
                    ax2.set_ylabel("Norma do resíduo (log JEDI)")
                    ax2.spines["top"].set_visible(False)
                    lines1, labels1 = ax.get_legend_handles_labels()
                    lines2, labels2 = ax2.get_legend_handles_labels()
                    ax.legend(lines1 + lines2, labels1 + labels2,
                              loc="upper right", frameon=False, fontsize=9)
                else:
                    ax.legend(loc="upper right", frameon=False, fontsize=9)
                ax.set_xlabel("Iteração do minimizador DRPCG")
                ax.set_ylabel("Função custo (unidades do JEDI)")
                ax.set_xticks(x)
                ax.grid(axis="y", color=GRID, alpha=.65, lw=.8)
                save(fig, output, f"jedi_cost_components_{detailed}")
                plt.close(fig)
                names.append(f"jedi_cost_components_{detailed}.png")
    return names
