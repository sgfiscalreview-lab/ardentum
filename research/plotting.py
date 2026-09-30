"""Plain, print-friendly figures in Ardentum's palette (no gradients, no chart junk)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SERIES = ["#1f4f82", "#b06a1f", "#2f7068", "#9e3a2c", "#677629", "#5a6472", "#8a6a4a", "#4a82b4"]
INK = "#1d1e20"
PAPER = "#f8f7f3"
GRID = "#dfdbd2"


def figure(width: float = 7.5, height: float = 4.2):  # type: ignore[no-untyped-def]
    fig, ax = plt.subplots(figsize=(width, height), dpi=150)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK)
    ax.tick_params(colors=INK, labelsize=8)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    return fig, ax


def save(fig, path: Path) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
