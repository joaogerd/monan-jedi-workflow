"""Read-only O-B/O-A time-series figures for completed MPAS-JEDI campaigns.

Feedback is paired by observation and intersected QC, using the same numerical
contract as scientific_feedback.paired_feedback. This assesses observation fit,
not forecast skill, and never initiates PBS jobs.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import re
import sys

import yaml

from .scientific_feedback import paired_feedback

_CYCLE_ID = re.compile(r"^\d{8}T\d{6}Z$")
_FIELDS = ("cycle", "observer", "variable", "units", "n",
           "omb_bias", "oma_bias", "omb_rmse", "oma_rmse", "file")
_OBSERVERS = {
    "obsout_3dvar_sondes.nc4": "sondes",
    "obsout_3dvar_sfc.nc4": "superficie",
    "obsout_3dvar_gnssroref.nc4": "gnssro",
}


def _expected_cycles(root: Path) -> list[str]:
    campaign = root / "campaign.yaml"
    if not campaign.is_file():
        raise ValueError(f"Campaign not found: {campaign}")
    calendar = yaml.safe_load(campaign.read_text())["calendar"]
    start = datetime.strptime(calendar["start"], "%Y-%m-%dT%H:%M:%SZ")
    end = datetime.strptime(calendar["end"], "%Y-%m-%dT%H:%M:%SZ")
    match = re.fullmatch(r"PT([1-9][0-9]*)H", calendar["interval"])
    if not match:
        raise ValueError("Only positive whole-hour campaign cycles are supported")
    step = timedelta(hours=int(match[1]))
    if end < start or (end - start) % step:
        raise ValueError("Campaign calendar has an invalid end/interval")
    count = int((end - start) / step) + int(calendar.get("end_inclusive", True))
    if count < 1 or count > 10000:
        raise ValueError("Campaign must contain between 1 and 10000 cycles")
    return [(start + i * step).strftime("%Y%m%dT%H%M%SZ")
            for i in range(count)]


def _variables(path: Path) -> list[str]:
    from netCDF4 import Dataset

    with Dataset(path) as ds:
        needed = ("ObsValue", "hofx0", "hofx1")
        if any(name not in ds.groups for name in needed):
            raise ValueError("Feedback missing ObsValue, hofx0 or hofx1")
        candidates = set(ds.groups["ObsValue"].variables)
        for name in needed[1:]:
            candidates.intersection_update(ds.groups[name].variables)
        return sorted(candidates)


def collect(root: Path, wanted: set[str] | None = None) -> dict:
    """Inspect files from known cycle directories; preserve absent/invalid evidence."""
    root = root.expanduser().resolve()
    cycles = _expected_cycles(root)
    rows = []
    missing = []
    skipped = []
    for cycle in cycles:
        folder = root / "work" / "jedi" / cycle / "Data" / "os"
        for name, observer in _OBSERVERS.items():
            path = folder / name
            if not path.is_file():
                missing.append({"cycle": cycle, "observer": observer, "path": str(path)})
                continue
            try:
                variables = _variables(path)
            except (OSError, RuntimeError, ValueError) as error:
                skipped.append({"cycle": cycle, "observer": observer,
                                "path": str(path), "error": str(error)})
                continue
            if wanted is not None:
                variables = [v for v in variables if v in wanted]
            for variable in variables:
                try:
                    result = paired_feedback(path, variable)
                except (OSError, RuntimeError, ValueError) as error:
                    skipped.append({"cycle": cycle, "observer": observer,
                                    "variable": variable, "path": str(path),
                                    "error": str(error)})
                    continue
                rows.append({field: result[field] for field in (
                    "variable", "units", "n", "omb_bias", "oma_bias",
                    "omb_rmse", "oma_rmse") } | {
                        "cycle": cycle, "observer": observer, "file": str(path)
                    })
    return {"experiment": str(root), "cycles_expected": len(cycles),
            "cycles": cycles, "rows": rows, "missing": missing, "skipped": skipped,
            "method": "paired ObsValue-hofx0/hofx1; finite values; EffectiveQC intersection 0",
            "interpretation": "observation fit only; not forecast skill"}


def render(report: dict, output: Path) -> list[str]:
    """Write CSV, JSON and one PNG per observer/variable with paired samples."""
    output.mkdir(parents=True, exist_ok=True)
    with (output / "paired_feedback.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(report["rows"])
    grouped = defaultdict(list)
    for row in report["rows"]:
        grouped[(row["observer"], row["variable"], row["units"])].append(row)
    generated = []
    if grouped:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError as error:
            raise RuntimeError(
                "matplotlib is required for PNG figures: pip install -e '.[plots]'"
            ) from error
        from .plot_style import BLUE, TEAL, GRID, MUTED, dates, heading, save, style, time_axis
        import numpy as np
        from matplotlib.ticker import MaxNLocator
        with style():
            for (observer, variable, units), rows in sorted(grouped.items()):
                rows.sort(key=lambda row: row["cycle"])
                times = dates([r["cycle"] for r in rows])
                b = np.asarray([r["omb_rmse"] for r in rows], dtype=float)
                a = np.asarray([r["oma_rmse"] for r in rows], dtype=float)
                bias_b = np.asarray([r["omb_bias"] for r in rows], dtype=float)
                bias_a = np.asarray([r["oma_bias"] for r in rows], dtype=float)
                count = np.asarray([r["n"] for r in rows], dtype=int)
                improved = int(np.count_nonzero(a <= b))
                mean_b, mean_a = float(b.mean()), float(a.mean())
                relative = 100 * (1 - mean_a / mean_b) if mean_b > 0 else float("nan")
                label = {
                    "sondes": "Radiossondas", "superficie": "Superfície",
                    "gnssro": "GNSS-RO",
                }.get(observer, observer)
                name = {
                    "airTemperature": "Temperatura do ar",
                    "specificHumidity": "Umidade específica",
                    "windEastward": "Vento zonal",
                    "windNorthward": "Vento meridional",
                    "stationPressure": "Pressão à superfície",
                    "atmosphericRefractivity": "Refratividade atmosférica",
                }.get(variable, variable)

                fig, axes = plt.subplots(3, 1, figsize=(12.2, 10.0), sharex=True,
                                         gridspec_kw={"height_ratios": [1.4, 1, .8]})
                fig.subplots_adjust(left=.09, right=.975, bottom=.1, top=.825, hspace=.16)
                heading(fig, f"Consistência observacional — {label}",
                        f"{name} • O−A ≤ O−B em {improved}/{len(rows)} ciclos"
                        f" • redução das médias de RMSE = {relative:.1f}%",
                        left=.09)
                axes[0].plot(times, b, color=BLUE, lw=2.2, marker="o", ms=5,
                             mfc="white", mew=1.7, label="O−B — background")
                axes[0].plot(times, a, color=TEAL, lw=2.2, marker="o", ms=5,
                             mfc="white", mew=1.7, label="O−A — análise")
                axes[0].fill_between(times, a, b, color=TEAL, alpha=.09,
                                     label="_nolegend_")
                axes[0].axhline(mean_b, color=BLUE, lw=1, ls="--", alpha=.55)
                axes[0].axhline(mean_a, color=TEAL, lw=1, ls="--", alpha=.55)
                axes[0].set_ylabel(f"RMSE ({units})")
                axes[0].legend(loc="upper right", frameon=False, ncol=2, fontsize=10)
                axes[0].text(.015, .045,
                             f"RMSE médio\nO−B   {mean_b:.4g}\nO−A   {mean_a:.4g}",
                             transform=axes[0].transAxes, va="bottom", color=MUTED,
                             bbox={"boxstyle": "round,pad=.45", "facecolor": "white",
                                   "edgecolor": GRID, "alpha": .96})

                axes[1].plot(times, bias_b, color=BLUE, lw=1.8, marker="o", ms=4,
                             mfc="white", label="O−B")
                axes[1].plot(times, bias_a, color=TEAL, lw=1.8, marker="o", ms=4,
                             mfc="white", label="O−A")
                axes[1].axhline(0, color=MUTED, lw=.85)
                axes[1].set_ylabel(f"Viés ({units})")
                axes[1].legend(loc="upper right", ncol=2, frameon=False)
                axes[2].plot(times, count, color=BLUE, lw=1.9, marker="o", ms=4,
                             mfc="white")
                axes[2].set_ylabel("Pares QC=0")
                axes[2].yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
                time_axis(axes[2], times)
                for axis in axes:
                    axis.grid(axis="y", color=GRID, alpha=.65, lw=.8)
                slug = re.sub(r"[^A-Za-z0-9_.-]+", "_",
                              f"{observer}_{variable}")
                save(fig, output, slug)
                plt.close(fig)
                generated.append(f"{slug}.png")
    from .campaign_evidence import collect_evidence, render_evidence
    evidence = collect_evidence(Path(report["experiment"]), report["cycles"])
    generated.extend(render_evidence(evidence, output))
    summary = {key: val for key, val in report.items() if key != "rows"}
    summary["operational_and_variational"] = {
        "campaign_complete": evidence["campaign_complete"],
        "workflow": evidence["workflow"],
        "cycles_with_cost": len(evidence["convergence"]),
        "cycles_monotonic": sum(row["monotonic"] for row in evidence["convergence"]),
        "mean_J_reduction_percent": (
            sum(row["reduction_percent"] for row in evidence["convergence"])
            / len(evidence["convergence"]) if evidence["convergence"] else None),
        "gaps": evidence["gaps"],
    }
    summary["figures"] = generated
    summary["paired_records"] = len(report["rows"])
    (output / "manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    op = summary["operational_and_variational"]
    cost_coverage = op["cycles_with_cost"]
    mean = op["mean_J_reduction_percent"]
    mean_text = f"{mean:.2f}%" if mean is not None else "indisponível"
    lines = [
        "# Diagnóstico MONAN-JEDI — campanha",
        "",
        f"- Ciclos esperados: {report['cycles_expected']}",
        f"- Continuidade operacional comprovada: {'sim' if op['campaign_complete'] else 'não'}",
        f"- Ciclos com função custo legível: {cost_coverage}/{report['cycles_expected']}",
        f"- Ciclos com J monotonicamente não crescente: {op['cycles_monotonic']}/{cost_coverage}",
        f"- Redução média da função custo: {mean_text}",
        f"- Estatísticas O–B/O–A por ciclo/variável: {len(report['rows'])}",
        f"- Arquivos observacionais ausentes: {len(report['missing'])}",
        f"- Variáveis observacionais ignoradas: {len(report['skipped'])}",
        f"- Lacunas operacionais/variacionais: {len(op['gaps'])}",
        "",
        "As estatísticas O–B/O–A referem-se às observações assimiladas e não à verificação independente.",
        "Convergência do minimizador e conclusão operacional não demonstram habilidade preditiva.",
        "As lacunas completas e referências aos arquivos estão em manifest.json.",
        "",
        "## Figuras",
        "",
    ]
    lines.extend(f"- {name}" for name in generated)
    (output / "report.md").write_text("\n".join(lines) + "\n")
    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="experiment plots",
                                     description="Scientific O-B/O-A plots; read-only inputs, no PBS")
    parser.add_argument("experiment", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--variables", default=None,
                        help="Comma-separated IODA variable names; default: all compatible")
    args = parser.parse_args(argv)
    root = args.experiment.expanduser().resolve()
    destination = args.output or root / "diagnostics" / "figures"
    wanted = ({s.strip() for s in args.variables.split(",") if s.strip()}
              if args.variables else None)
    try:
        report = collect(root, wanted)
        figures = render(report, destination)
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(f"[ERRO] Não foi possível gerar figuras: {error}", file=sys.stderr)
        return 2
    print(f"[INFO] Ciclos esperados: {report['cycles_expected']}")
    print(f"[INFO] Séries por ciclo/observador/variável: {len(report['rows'])}")
    print(f"[INFO] Arquivos ausentes: {len(report['missing'])}; "
          f"variáveis/arquivos ignorados: {len(report['skipped'])}")
    print(f"[INFO] CSV e manifesto: {destination}")
    op = json.loads((destination / "manifest.json").read_text())["operational_and_variational"]
    print(f"[INFO] Convergência J: {op['cycles_with_cost']}/{report['cycles_expected']} ciclos; "
          f"continuidade validada: {op['campaign_complete']}")
    if not figures:
        print("[AVISO] Nenhuma figura gerada: feedback O-B/O-A utilizável não encontrado. "
              "Consulte manifest.json para lacunas e erros.", file=sys.stderr)
        return 2
    print(f"[OK] {len(figures)} figura(s) PNG gerada(s) em {destination}")
    print("[NOTA] O-B/O-A mede ajuste às observações, não habilidade de previsão.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
