"""Plot directly relevant published human benchmarks beside model responses."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import plot_style  # noqa: E402,F401

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
PLOT_OUT = ROOT / "writeup" / "plots" / "published_human_benchmarks.png"

HUMAN = "#657786"
PERSIMMON = plot_style.DIVERGING2[0]
GPT6 = plot_style.DIVERGING2[1]


def draw_panel(ax, title, rows):
    y = list(range(len(rows)))
    values = [row[1] for row in rows]
    labels = [row[0] for row in rows]
    colors = [row[2] for row in rows]
    bars = ax.barh(y, values, color=colors, height=0.66)
    for bar, row in zip(bars, rows):
        ax.text(
            bar.get_width() + 1.2,
            bar.get_y() + bar.get_height() / 2,
            f"{row[1]:.0f}% (n={row[3]})",
            va="center",
            ha="left",
            fontsize=10,
        )
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 110)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xlabel("Share selecting the named response (%)")
    ax.set_title(title)


def main() -> None:
    fig, axes = plt.subplots(1, 2, figsize=plot_style.FIGSIZE["two_wide"])
    draw_panel(
        axes[0],
        "Linda: conjunction chosen",
        [
            ("Tversky & Kahneman 1983", 85, HUMAN, 142),
            ("Oechssler et al. 2009: lower CRT", 62.6, HUMAN, 157),
            ("Oechssler et al. 2009: higher CRT", 38.3, HUMAN, 407),
            ("Persimmon v0.1", 100 * 8 / 12, PERSIMMON, 12),
            ("GPT-6.2-Sol", 0, GPT6, 12),
        ],
    )
    draw_panel(
        axes[1],
        "Bat-and-ball: intuitive $0.10 answer",
        [
            ("Oechssler et al. 2009", 40.2, HUMAN, 564),
            ("Persimmon v0.1", 100 * 2 / 12, PERSIMMON, 12),
            ("GPT-6.2-Sol", 0, GPT6, 12),
        ],
    )
    plot_style.save(fig, PLOT_OUT)
    plt.close(fig)
    print(PLOT_OUT)


if __name__ == "__main__":
    main()
