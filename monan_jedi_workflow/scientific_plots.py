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
        for (observer, variable, units), rows in sorted(grouped.items()):
            rows.sort(key=lambda row: row["cycle"])
            names = ["omb_rmse", "oma_rmse", "omb_bias", "oma_bias", "n"]
            times = [datetime.strptime(row["cycle"], "%Y%m%dT%H%M%SZ")
                     for row in rows]
            fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
            axes[0].plot(times, [r["omb_rmse"] for r in rows],
                         marker=".", label="O-B")
            axes[0].plot(times, [r["oma_rmse"] for r in rows],
                         marker=".", label="O-A")
            axes[0].set_ylabel(f"RMSE ({units})")
            axes[0].legend()
            axes[1].plot(times, [r["omb_bias"] for r in rows],
                         marker=".", label="O-B")
            axes[1].plot(times, [r["oma_bias"] for r in rows],
                         marker=".", label="O-A")
            axes[1].axhline(0, linewidth=0.8, color="gray")
            axes[1].set_ylabel(f"Viés ({units})")
            axes[1].legend()
            axes[2].plot(times, [r["n"] for r in rows], marker=".")
            axes[2].set_ylabel("Observações pareadas (QC=0)")
            axes[2].set_xlabel("Ciclo UTC")
            for axis in axes:
                axis.grid(True, alpha=0.25)
            fig.suptitle(f"{observer} · {variable} · O-B/O-A pareados")
            fig.autofmt_xdate()
            fig.tight_layout()
            slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{observer}_{variable}")
            filename = f"{slug}.png"
            fig.savefig(output / filename, dpi=150)
            plt.close(fig)
            generated.append(filename)
    summary = {key: val for key, val in report.items() if key != "rows"}
    summary["figures"] = generated
    summary["paired_records"] = len(report["rows"])
    (output / "manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
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
    if not figures:
        print("[AVISO] Nenhuma figura gerada: feedback O-B/O-A utilizável não encontrado. "
              "Consulte manifest.json para lacunas e erros.", file=sys.stderr)
        return 2
    print(f"[OK] {len(figures)} figura(s) PNG gerada(s) em {destination}")
    print("[NOTA] O-B/O-A mede ajuste às observações, não habilidade de previsão.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
