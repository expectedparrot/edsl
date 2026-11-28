"""Create report figures from the saved Persimmon/GPT-6 comparison summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import plot_style  # noqa: E402,F401

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "analysis" / "summary_model_comparison.json"
PLOT_DIR = ROOT / "writeup" / "plots"

LABELS = {
    "linda_conjunction": {
        "Linda is a bank teller.": "Bank teller alone",
        "Linda is a bank teller and active in a feminist organization.": "Bank teller + activist",
    },
    "occupation_base_rate": {
        "Lawyer": "Lawyer",
        "Engineer": "Engineer",
        "Equally likely": "Equally likely",
    },
    "taxi_bayes": {
        "Blue taxi": "Blue taxi",
        "Green taxi": "Green taxi",
        "Equally likely": "Equally likely",
    },
    "bat_ball": {"$0.05": "$0.05", "$0.10": "$0.10"},
}


def load_summary() -> dict:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def build_answer_distributions(summary: dict) -> None:
    model_labels = ["Persimmon v0.1", "GPT-6.2-Sol"]
    model_colors = plot_style.DIVERGING2
    fig, axes = plt.subplots(2, 2, figsize=plot_style.FIGSIZE["two_wide"])
    for ax, item in zip(axes.flat, summary["items"]):
        key = item["name"]
        pers = item["persimmon_answer_counts"]
        gpt = item["gpt6_answer_counts"]
        options = list(LABELS[key])
        if key == "bat_ball" and any(
            answer not in LABELS[key] and answer != "<missing>"
            for answer in (*pers, *gpt)
        ):
            options.append("Other")
        y = np.arange(len(options))
        height = 0.34
        pers_values = [
            sum(
                count
                for answer, count in pers.items()
                if answer not in LABELS[key] and answer != "<missing>"
            )
            if option == "Other"
            else pers.get(option, 0)
            for option in options
        ]
        gpt_values = [
            sum(
                count
                for answer, count in gpt.items()
                if answer not in LABELS[key] and answer != "<missing>"
            )
            if option == "Other"
            else gpt.get(option, 0)
            for option in options
        ]
        b1 = ax.barh(y + height / 2, pers_values, height, color=model_colors[0])
        b2 = ax.barh(y - height / 2, gpt_values, height, color=model_colors[1])
        for bars in (b1, b2):
            for bar in bars:
                value = int(bar.get_width())
                ax.text(
                    value + 0.12,
                    bar.get_y() + bar.get_height() / 2,
                    str(value),
                    va="center",
                    ha="left",
                    fontsize=10,
                )
        ax.set_yticks(y, [LABELS[key].get(option, option) for option in options])
        ax.invert_yaxis()
        ax.set_xlim(0, 13.7)
        ax.set_xticks(range(0, 13, 3))
        ax.set_xlabel("Valid responses (count)")
        ax.set_title(item["concept"])
        if key == "occupation_base_rate":
            ax.text(
                0.99,
                0.02,
                "GPT-6.2-Sol: 11 valid / 12",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=10,
                color="#555555",
            )
    fig.legend(
        [plt.Rectangle((0, 0), 1, 1, color=color) for color in model_colors],
        model_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=2,
        frameon=False,
    )
    plot_style.save(fig, PLOT_DIR / "answer_distributions.png")
    plt.close(fig)


def build_normative_shares(summary: dict) -> None:
    model_labels = ["Persimmon v0.1", "GPT-6.2-Sol"]
    colors = plot_style.DIVERGING2
    rows = summary["items"]
    y = np.arange(len(rows))
    height = 0.32
    fig, ax = plt.subplots(figsize=plot_style.figsize_stacked(4, width=11.5))
    for offset, model_key, color, label in (
        (height / 2, "persimmon_correct_on_common", colors[0], model_labels[0]),
        (-(height / 2), "gpt6_correct_on_common", colors[1], model_labels[1]),
    ):
        counts = [item[model_key] for item in rows]
        denominators = [item["common_support_n"] for item in rows]
        shares = [100 * count / n for count, n in zip(counts, denominators)]
        bars = ax.barh(y + offset, shares, height, color=color, label=label)
        for bar, count, denominator in zip(bars, counts, denominators):
            ax.text(
                min(bar.get_width() + 1.5, 103),
                bar.get_y() + bar.get_height() / 2,
                f"{count}/{denominator}",
                va="center",
                ha="left",
                fontsize=10,
            )
    ax.set_yticks(y, [item["concept"] for item in rows])
    ax.invert_yaxis()
    ax.tick_params(axis="y", labelsize=12)
    ax.set_xlim(0, 115)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xlabel("Normative answer selected (%)")
    ax.set_title("Normative answer choices were more common with GPT-6.2-Sol")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.13), ncol=2, frameon=False)
    plot_style.save(fig, PLOT_DIR / "normative_answer_share.png")
    plt.close(fig)


def main() -> None:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    summary = load_summary()
    build_answer_distributions(summary)
    build_normative_shares(summary)
    print(json.dumps({"plots": [str(p) for p in sorted(PLOT_DIR.glob("*.png"))]}, indent=2))


if __name__ == "__main__":
    import json

    main()
