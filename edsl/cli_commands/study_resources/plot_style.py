"""
plot_style.py — Shared matplotlib style baseline for EP-Agent report visuals.

USAGE
-----
Copy this file into your study's analysis/ directory, then add to the top
of every plot script:

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import plot_style          # noqa: F401  (side-effects only)

That single import applies all defaults.  No further setup needed.

WHAT IT DOES
------------
- Sets rcParams for fonts, sizes, padding, and grid style
- Provides helper functions for common layout tasks
- Enforces consistent color palettes across the study
"""

from __future__ import annotations
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np

EP_GREEN = "#3A9E5F"


def apply_style() -> None:
    """Compatibility entry point; importing this module already applies the style."""
    mpl.rcParams.update({"font.family": "DejaVu Serif", "figure.dpi": 150, "savefig.dpi": 150})

# ---------------------------------------------------------------------------
# 1. Global rcParams
# ---------------------------------------------------------------------------
mpl.rcParams.update(
    {
        # --- Font ---
        # DejaVu Serif matches the Latin Modern Roman used in LaTeX/pandoc-compiled
        # report PDFs. Using a serif font here prevents the visual mismatch between
        # plot text (sans-serif) and surrounding report body text (serif).
        "font.family": "DejaVu Serif",
        "font.size": 11,                # default for all text
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlepad": 10,
        "axes.labelsize": 12,
        "axes.labelweight": "normal",
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "legend.title_fontsize": 11,
        "figure.titlesize": 15,
        "figure.titleweight": "bold",
        # --- Layout ---
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.15,
        "figure.constrained_layout.use": False,  # we call tight_layout() explicitly
        "figure.autolayout": False,
        # --- Axes ---
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.axisbelow": True,
        # --- Lines / bars ---
        "lines.linewidth": 1.8,
        "patch.linewidth": 0.6,
        "patch.edgecolor": "white",
        # --- Color cycle ---
        "axes.prop_cycle": mpl.cycler(
            color=[
                "#2C6FAC",  # blue
                "#E05A2B",  # orange
                "#3A9E5F",  # green
                "#9B4DCA",  # purple
                "#C0392B",  # red
                "#1A7F8E",  # teal
                "#E8A838",  # amber
                "#5D6D7E",  # steel grey
            ]
        ),
    }
)


# ---------------------------------------------------------------------------
# 2. Recommended figure sizes
# ---------------------------------------------------------------------------
# Use these as the figsize argument to plt.subplots() or plt.figure()

FIGSIZE = {
    "single":       (10, 6),    # one panel
    "two_wide":     (14, 6),    # two panels side by side
    "three_wide":   (16, 5),    # three panels side by side
    "two_tall":     (8, 11),    # two panels stacked
    "square":       (8, 8),     # one square panel (e.g. heatmap)
    "wide_banner":  (16, 4),    # wide single row
}

# Stacked subplot panels: figure height = N_rows * ROW_HEIGHT_PER_PANEL
# Use figsize_stacked() when each row is a SEPARATE SUBPLOT (its own axes).
# Use figsize_likert()  when all bars share ONE axes (e.g. a Likert chart).
ROW_HEIGHT_PER_PANEL = 2.8


def figsize_stacked(n_rows: int, width: float = 12.0) -> tuple[float, float]:
    """Return a good figsize for n_rows stacked SUBPLOT PANELS (each row is its own axes)."""
    return (width, max(n_rows * ROW_HEIGHT_PER_PANEL, 4.0))


def figsize_likert(n_rows: int, width: float = 14.0) -> tuple[float, float]:
    """
    Return a good figsize for a single-axes horizontal bar chart with n_rows bars.

    Use this for Likert / stacked percent charts where all bars share one axes.
    Do NOT use figsize_stacked() for this — it creates far too much whitespace.

    Formula: height = 1.3 * n_rows + 2.5  (leaves room for title and legend below)
    """
    height = max(1.3 * n_rows + 2.5, 5.0)
    return (width, height)


def set_chart_title(
    ax: "plt.Axes",
    title: str,
    subtitle: str = "",
) -> None:
    """
    Set a title and optional subtitle on a single-panel chart.

    ALWAYS use this instead of mixing fig.suptitle() + ax.set_title().

    WHY: fig.suptitle() centers on the full figure width.  ax.set_title()
    centers on the axes width.  When the axes has wide y-tick labels (e.g.,
    Likert charts with "All respondents"), the axes is inset and its center
    is shifted right relative to the figure center.  The two title lines then
    appear misaligned even though they are both nominally "centered".

    This helper anchors BOTH lines to the axes center, so they always align.

    For multi-panel charts, fig.suptitle() for the overall title and
    ax.set_title() per panel is correct — do not use this helper there.

    Parameters
    ----------
    ax       : the single axes to title
    title    : main headline (bold, axes.titlesize = 14pt by default)
    subtitle : optional second line (normal weight, 13pt by default)
    """
    ts = int(mpl.rcParams.get("axes.titlesize", 14))
    ss = ts - 1  # subtitle slightly smaller

    if subtitle:
        # Main title with extra top padding to leave room for subtitle line
        ax.set_title(title, fontsize=ts, fontweight="bold", pad=ss * 2.2)
        # Subtitle anchored to top of axes (axes fraction y=1.0) — same x
        # reference as set_title, so both lines are guaranteed to align.
        ax.text(
            0.5, 1.0,
            subtitle,
            transform=ax.transAxes,
            ha="center", va="bottom",
            fontsize=ss, fontweight="normal",
        )
    else:
        ax.set_title(title, fontsize=ts, fontweight="bold")


# ---------------------------------------------------------------------------
# 3. Standard color palettes
# ---------------------------------------------------------------------------

# 5-level Likert (negative → positive)
LIKERT5_COLORS = ["#C0392B", "#E08080", "#F5E642", "#80C080", "#27AE60"]

# 7-level Likert
LIKERT7_COLORS = [
    "#922B21", "#C0392B", "#E08080",
    "#BDC3C7",
    "#80C080", "#27AE60", "#1A6B3A",
]

# Diverging (2-group contrast)
DIVERGING2 = ["#2C6FAC", "#E05A2B"]

# Neutral categorical sequence (up to 8)
CATEGORICAL = [
    "#2C6FAC", "#E05A2B", "#3A9E5F", "#9B4DCA",
    "#C0392B", "#1A7F8E", "#E8A838", "#5D6D7E",
]

# Greyscale for print-safe figures
GREYSCALE = ["#222222", "#555555", "#888888", "#AAAAAA", "#CCCCCC"]


# ---------------------------------------------------------------------------
# 4. Helper: annotate bars with percentage or value labels
# ---------------------------------------------------------------------------

def label_bars(
    ax: plt.Axes,
    bars,
    fmt: str = "{:.0f}%",
    min_val: float = 3.0,
    offset: float = 0.5,
    fontsize: int = 10,
    color: str = "black",
    fontweight: str = "bold",
) -> None:
    """
    Add value labels above (or inside) each bar.

    Parameters
    ----------
    bars      : BarContainer returned by ax.bar() or ax.barh()
    fmt       : format string, receives the bar height/width as a float
    min_val   : bars narrower than this are skipped (avoids clutter)
    offset    : gap in data units between bar tip and label
    fontsize  : label font size (never set below 9)
    """
    fontsize = max(fontsize, 9)
    for bar in bars:
        val = bar.get_height() if bar.get_height() != 0 else bar.get_width()
        if abs(val) < min_val:
            continue
        x = bar.get_x() + bar.get_width() / 2
        y = bar.get_height() + offset
        ax.text(
            x, y, fmt.format(val),
            ha="center", va="bottom",
            fontsize=fontsize, fontweight=fontweight, color=color,
        )


def label_hbars(
    ax: plt.Axes,
    bars,
    fmt: str = "{:.0f}%",
    min_val: float = 3.0,
    offset: float = 0.5,
    fontsize: int = 10,
    color: str = "black",
    fontweight: str = "bold",
) -> None:
    """Add value labels to the right of horizontal bars."""
    fontsize = max(fontsize, 9)
    for bar in bars:
        val = bar.get_width()
        if abs(val) < min_val:
            continue
        x = val + offset
        y = bar.get_y() + bar.get_height() / 2
        ax.text(
            x, y, fmt.format(val),
            ha="left", va="center",
            fontsize=fontsize, fontweight=fontweight, color=color,
        )


# ---------------------------------------------------------------------------
# 5. Helper: rotate or wrap x-tick labels to prevent overlap
# ---------------------------------------------------------------------------

def fix_xtick_labels(
    ax: plt.Axes,
    max_chars: int = 12,
    rotation: int = 30,
    ha: str = "right",
) -> None:
    """
    If any x-tick label is longer than max_chars, rotate all of them.
    Call this after setting tick labels.
    """
    labels = [t.get_text() for t in ax.get_xticklabels()]
    if any(len(lbl) > max_chars for lbl in labels):
        ax.set_xticklabels(labels, rotation=rotation, ha=ha, fontsize=10)


def wrap_labels(labels: list[str], width: int = 12) -> list[str]:
    """
    Word-wrap a list of tick labels to at most `width` chars per line.
    Useful for long category names on bar charts.
    """
    import textwrap
    return ["\n".join(textwrap.wrap(lbl, width)) for lbl in labels]


# ---------------------------------------------------------------------------
# 6. Helper: finalize and save
# ---------------------------------------------------------------------------

def save(fig: plt.Figure, path, tight: bool = True) -> None:
    """
    Save figure with standard settings.

    Parameters
    ----------
    path  : str or Path — destination file (PNG recommended)
    tight : bool — call tight_layout() before saving (default True)
    """
    import pathlib
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if tight:
        try:
            fig.tight_layout()
        except Exception:
            pass  # constrained_layout may conflict; ignore
    fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.15)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# 7. Helper: stacked-bar percent chart (common in survey work)
# ---------------------------------------------------------------------------

def stacked_pct_hbar(
    ax: plt.Axes,
    label: str,
    fractions: list[float],
    colors: list[str],
    option_labels: list[str],
    min_pct_for_text: float = 7.0,
    fontsize: int = 13,
    bar_height: float = 0.7,
) -> None:
    """
    Draw a single horizontal stacked-percent bar on `ax`.

    Call once per row; all rows share the same `ax`.
    Use figsize_likert(n_rows) for the figure size — NOT figsize_stacked().

    Parameters
    ----------
    label            : y-axis label for this bar (e.g. role name, concept name)
    fractions        : list of percentages — must sum to ~100
    colors           : one color per fraction
    option_labels    : one label per fraction (used for legend; not drawn on bars)
    min_pct_for_text : skip annotation if segment is narrower than this % (default 7)
    fontsize         : in-bar annotation font size (default 13 — never go below 11)
    bar_height       : bar thickness as fraction of categorical unit (default 0.7)

    IMPORTANT: pass the label string (not 0) as y-coordinate to ax.text() —
    see 'Known pitfall' in research_agent/skills/report-authoring/SKILL.md.
    """
    fontsize = max(fontsize, 11)
    left = 0.0
    for frac, color in zip(fractions, colors):
        ax.barh([label], [frac], left=left, color=color, height=bar_height)
        if frac >= min_pct_for_text:
            ax.text(
                left + frac / 2, label,
                f"{frac:.0f}%",
                ha="center", va="center",
                fontsize=fontsize, fontweight="bold", color="black",
            )
        left += frac
    ax.set_xlim(0, 100)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_xlabel("% of respondents", fontsize=13)

