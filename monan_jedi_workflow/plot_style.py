"""Institutional M3 figure style (docs/relatorios/padrao_figuras.md).

Formatting and export only. This module never alters scientific data.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

INK = "#111827"
MUTED = "#6b7280"
GRID = "#d1d5db"
BLUE = "#355f8d"
TEAL = "#159d82"
GREEN = "#18864b"


@contextmanager
def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with plt.rc_context({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": "#4b5563",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    }):
        yield plt


def heading(fig, title: str, subtitle: str, *, left: float = 0.08) -> None:
    """Keep 30 points between title and subtitle irrespective of figure height."""
    fig.text(left, .973, title, fontsize=17, weight="bold", va="top", color=INK)
    fig.text(left, .973 - 30 / (72 * fig.get_figheight()), subtitle,
             fontsize=10.5, va="top", color=MUTED)


def dates(cycles: list[str]):
    return [datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            for s in cycles]


def time_axis(ax, dates_utc, max_ticks=11):
    import matplotlib.dates as mdates
    import numpy as np

    if not dates_utc:
        return
    stride = max(1, int(np.ceil(max(1, len(dates_utc) - 1) / max(1, max_ticks - 1))))
    indexes = list(range(0, len(dates_utc), stride))
    if indexes[-1] != len(dates_utc) - 1:
        indexes.append(len(dates_utc) - 1)
    ax.set_xticks([dates_utc[i] for i in indexes])
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%HZ", tz=timezone.utc))
    ax.set_xlabel("Ciclo de análise (UTC)", labelpad=8)
    ax.margins(x=.018)


def save(fig, output: Path, name: str) -> None:
    """Write publication-ready PNG/PDF/SVG from exactly the same figure."""
    output.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(output / f"{name}.{suffix}", dpi=200,
                    bbox_inches="tight")
