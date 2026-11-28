"""Summarize model distributions and compare them with published summaries."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, quantiles

import matplotlib.pyplot as plt
import numpy as np


PERSIMMON = "persimmon-v0.1"
GPT = "gpt-6.2-sol"
MODELS = [PERSIMMON, GPT]
MODEL_COLORS = {PERSIMMON: "#6c4ab6", GPT: "#167d9a"}
HUMAN_COLOR = "#727b84"
LINDA_CONJUNCTION = "Linda is a bank teller and is active in the feminist movement."
LINDA_SINGLE = "Linda is a bank teller."
PROFILE_ANSWERS = {
    "Jack": "answer.jack_probability",
    "Dick": "answer.dick_probability",
    "No information": "answer.null_probability",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def is_missing(value: str | None) -> bool:
    return value is None or value.strip().lower() in {"", "none", "nan", "null", "<missing>"}


def parse_probability(value: str | None) -> float | None:
    if is_missing(value):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value or "")
    if not match:
        return None
    try:
        number = float(match.group())
    except ValueError:
        return None
    return number if 0 <= number <= 100 else None


def parse_money(value: str | None) -> float | None:
    if is_missing(value):
        return None
    text = (value or "").lower().replace(",", "")
    amount_pattern = r"\$?\s*(\d+(?:\.\d{1,3})?)\s*(cents?|¢)?"
    ball_patterns = (
        rf"\b(?:the\s+)?ball\s+(?:costs?|is|would cost|would be)\s*{amount_pattern}",
        rf"\bcost of (?:the )?ball is\s*{amount_pattern}",
    )
    for pattern in ball_patterns:
        matches = list(re.finditer(pattern, text))
        if matches:
            if len(matches) != 1:
                return None
            amount, unit = matches[0].groups()[-2:]
            try:
                result = float(amount)
            except ValueError:
                return None
            is_cents = (unit and unit.startswith("cent")) or unit == "¢"
            return result / 100 if is_cents else result

    word_cents = {
        "one cent": 0.01,
        "five cents": 0.05,
        "ten cents": 0.10,
    }
    for phrase, amount in word_cents.items():
        ball_phrase = rf"\b(?:the\s+)?ball\b[^.!?\n]{{0,60}}\b{re.escape(phrase)}\b"
        if re.search(ball_phrase, text):
            return amount
    candidates = [
        amount
        for phrase, amount in word_cents.items()
        if phrase in text
    ]
    for match in re.finditer(amount_pattern, text):
        raw_amount, unit = match.groups()
        amount = float(raw_amount)
        if unit and (unit.startswith("cent") or unit == "¢"):
            amount /= 100
        candidates.append(amount)
    if not candidates:
        return None
    unique = []
    for amount in candidates:
        if not any(math.isclose(amount, known, abs_tol=0.0001) for known in unique):
            unique.append(amount)
    return unique[0] if len(unique) == 1 else None


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def percentile_summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "median": None, "q1": None, "q3": None}
    if len(values) == 1:
        q1 = q3 = values[0]
    else:
        q1, q3 = quantiles(values, n=4, method="inclusive")[0::2]
    return {
        "n": len(values),
        "mean": round(mean(values), 3),
        "median": round(median(values), 3),
        "q1": round(q1, 3),
        "q3": round(q3, 3),
    }


def summarize_linda(rows_a: list[dict[str, str]], rows_b: list[dict[str, str]]) -> dict:
    output = {}
    for model in MODELS:
        by_form = {}
        pooled = []
        for label, rows in [("bank_teller_first", rows_a), ("conjunction_first", rows_b)]:
            answers = [row["answer.linda_choice"].strip() for row in rows if row.get("model.model") == model and not is_missing(row.get("answer.linda_choice"))]
            conjunction_n = sum(answer == LINDA_CONJUNCTION for answer in answers)
            teller_n = sum(answer == LINDA_SINGLE for answer in answers)
            valid_n = conjunction_n + teller_n
            low, high = wilson_interval(conjunction_n, valid_n)
            by_form[label] = {
                "n": len(answers),
                "valid_n": valid_n,
                "conjunction_n": conjunction_n,
                "bank_teller_n": teller_n,
                "conjunction_rate": conjunction_n / valid_n if valid_n else None,
                "ci95": [low, high],
            }
            pooled.extend(answers)
        conjunction_n = sum(answer == LINDA_CONJUNCTION for answer in pooled)
        valid_n = sum(answer in {LINDA_CONJUNCTION, LINDA_SINGLE} for answer in pooled)
        low, high = wilson_interval(conjunction_n, valid_n)
        output[model] = {
            "forms": by_form,
            "pooled": {
                "n": len(pooled),
                "valid_n": valid_n,
                "conjunction_n": conjunction_n,
                "bank_teller_n": valid_n - conjunction_n,
                "conjunction_rate": conjunction_n / valid_n if valid_n else None,
                "ci95": [low, high],
            },
        }
    return output


def summarize_engineer(rows: list[dict[str, str]]) -> dict:
    values: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    missing = Counter()
    observed = set()
    for row in rows:
        model = row.get("model.model", "")
        engineer_count = parse_probability(row.get("scenario.engineer_count"))
        target = (row.get("scenario.target_occupation") or "").strip().lower()
        if model not in MODELS or engineer_count not in (30, 70):
            continue
        condition = "low_engineer_prior" if engineer_count == 30 else "high_engineer_prior"
        for profile, answer_column in PROFILE_ANSWERS.items():
            observed.add((model, condition, profile))
            raw = parse_probability(row.get(answer_column))
            if raw is None:
                missing[(model, condition, profile)] += 1
                continue
            converted = 100.0 - raw if target == "lawyers" else raw
            values[model][condition][profile].append(converted)
    output = {}
    for model, condition, profile in sorted(observed):
        output.setdefault(model, {}).setdefault(condition, {})[profile] = {
            **percentile_summary(values[model][condition][profile]),
            "missing": missing[(model, condition, profile)],
        }
    return output


def summarize_batball(rows: list[dict[str, str]]) -> dict:
    output = {}
    for model in MODELS:
        categories = Counter()
        unparsed = 0
        total = 0
        for row in rows:
            if row.get("model.model") != model:
                continue
            total += 1
            amount = parse_money(row.get("answer.bat_ball_answer"))
            if amount is None:
                unparsed += 1
            elif math.isclose(amount, 0.05, abs_tol=0.005):
                categories["correct_$0.05"] += 1
            elif math.isclose(amount, 0.10, abs_tol=0.005):
                categories["intuitive_$0.10"] += 1
            else:
                categories["other_numeric"] += 1
        valid_n = sum(categories.values())
        output[model] = {
            "n": total,
            "valid_n": valid_n,
            "unparsed_or_missing": unparsed,
            "counts": dict(categories),
            "rates": {
                name: count / valid_n if valid_n else None
                for name, count in categories.items()
            },
        }
    return output


def plot_linda(summary: dict, output_dir: Path) -> None:
    labels = ["Published human", "Persimmon\nteller first", "Persimmon\nconjunction first", "GPT\nteller first", "GPT\nconjunction first"]
    values = [0.85]
    intervals = [wilson_interval(round(0.85 * 142), 142)]
    sample_sizes = [142]
    colors = [HUMAN_COLOR]
    for model in MODELS:
        for form in ["bank_teller_first", "conjunction_first"]:
            record = summary[model]["forms"][form]
            values.append(record["conjunction_rate"] or 0)
            intervals.append(tuple(record["ci95"]))
            sample_sizes.append(record["valid_n"])
            colors.append(MODEL_COLORS[model])

    x = np.arange(len(values))
    lower = [max(0, value - interval[0]) for value, interval in zip(values, intervals)]
    upper = [max(0, interval[1] - value) for value, interval in zip(values, intervals)]
    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    ax.bar(x, values, color=colors, width=0.68, edgecolor="white", linewidth=0.8)
    ax.errorbar(x, values, yerr=[lower, upper], fmt="none", ecolor="#26323a", capsize=4, linewidth=1.3)
    ax.axhline(0.85, color=HUMAN_COLOR, linestyle="--", linewidth=1.2, alpha=0.8)
    for i, (value, n) in enumerate(zip(values, sample_sizes)):
        ax.text(i, min(1.02, value + 0.055), f"{value:.0%}\nn={n}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Share choosing the conjunction")
    ax.set_title("Linda transparent test: conjunction choice by option order")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#d9dee3", linewidth=0.7)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output_dir / "linda_distribution.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_engineer(summary: dict, output_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.8), sharey=True)
    profiles = ["Jack", "Dick", "No information"]
    conditions = ["low_engineer_prior", "high_engineer_prior"]
    condition_labels = ["30 engineers /\n70 lawyers", "70 engineers /\n30 lawyers"]
    for ax, profile in zip(axes, profiles):
        series = []
        positions = []
        colors = []
        labels = []
        human_points = []
        next_pos = 1
        for model in MODELS:
            for condition_index, condition in enumerate(conditions):
                # Full model response distributions appear in the exported result rows.
                values = _engineer_raw_values_for_plot
                series.append(values[(model, condition, profile)])
                positions.append(next_pos)
                colors.append(MODEL_COLORS[model])
                labels.append(f"{model.split('-')[0]}\n{condition_labels[condition_index]}")
                next_pos += 1
                human_median = None
                if profile == "Dick":
                    human_median = 50
                elif profile == "No information":
                    human_median = 30 if condition == "low_engineer_prior" else 70
                if human_median is not None:
                    human_points.append((positions[-1], human_median))
        boxes = ax.boxplot(series, positions=positions, widths=0.58, patch_artist=True, showfliers=False, medianprops={"color": "#1f2933", "linewidth": 1.4})
        for box, color in zip(boxes["boxes"], colors):
            box.set_facecolor(color)
            box.set_alpha(0.48)
            box.set_edgecolor(color)
        for position, value in human_points:
            ax.scatter(position, value, marker="D", s=42, color="#111820", edgecolor="white", linewidth=0.7, zorder=4)
        ax.set_xticks(positions, labels, fontsize=8)
        ax.set_title(profile)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", color="#d9dee3", linewidth=0.7)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Estimated probability of engineer (%)")
    fig.suptitle("Engineer–lawyer task: partial replication", y=1.02, fontsize=15)
    fig.text(0.5, -0.01, "Black diamonds: published human medians where directly available (Dick=50%; no-information=30%/70%).\nOriginal five-profile mean: 50% low-prior, 55% high-prior; not specific to Jack or Dick.", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(output_dir / "engineer_lawyer_distributions.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


_engineer_raw_values_for_plot: dict[tuple[str, str, str], list[float]] = defaultdict(list)


def plot_batball(summary: dict, output_dir: Path) -> None:
    categories = ["correct_$0.05", "intuitive_$0.10", "other_numeric"]
    labels = ["Correct\n$0.05", "Intuitive\n$0.10", "Other numeric"]
    human_rates = [0.548, 0.402, 0.05]
    x = np.arange(len(categories))
    width = 0.24
    fig, ax = plt.subplots(figsize=(9.3, 5.2))
    ax.bar(x - width, human_rates, width, color=HUMAN_COLOR, label="Published human (N=564)")
    for model_index, model in enumerate(MODELS):
        rates = [summary[model]["rates"].get(category, 0) or 0 for category in categories]
        position = x + model_index * width
        ax.bar(position, rates, width, color=MODEL_COLORS[model], label=model)
        for px, rate in zip(position, rates):
            ax.text(px, rate + 0.012, f"{rate:.0%}", ha="center", va="bottom", fontsize=8)
    for px, rate in zip(x - width, human_rates):
        ax.text(px, rate + 0.012, f"{rate:.0%}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Share of valid numeric responses")
    ax.set_title("Bat-and-ball responses: free numeric answers")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#d9dee3", linewidth=0.7)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output_dir / "bat_ball_distribution.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--linda-a", required=True, type=Path)
    parser.add_argument("--linda-b", required=True, type=Path)
    parser.add_argument("--engineer", required=True, type=Path)
    parser.add_argument("--bat-ball", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()

    linda_a_rows = read_rows(args.linda_a)
    linda_b_rows = read_rows(args.linda_b)
    engineer_rows = read_rows(args.engineer)
    batball_rows = read_rows(args.bat_ball)

    # Preserve per-profile values for the boxplot while also computing summaries.
    for row in engineer_rows:
        model = row.get("model.model", "")
        engineer_count = parse_probability(row.get("scenario.engineer_count"))
        target = (row.get("scenario.target_occupation") or "").strip().lower()
        if model not in MODELS or engineer_count not in (30, 70):
            continue
        condition = "low_engineer_prior" if engineer_count == 30 else "high_engineer_prior"
        for profile, answer_column in PROFILE_ANSWERS.items():
            raw = parse_probability(row.get(answer_column))
            if raw is not None:
                _engineer_raw_values_for_plot[(model, condition, profile)].append(
                    100.0 - raw if target == "lawyers" else raw
                )

    summary = {
        "planned_sample_sizes": {
            "linda_per_model": 200,
            "engineer_lawyer_per_model_per_prior": 100,
            "bat_ball_per_model": 200,
        },
        "published_human_benchmarks": {
            "linda_conjunction_rate": 0.85,
            "linda_n": 142,
            "engineer_informative_profile_mean_low_prior": 50,
            "engineer_informative_profile_mean_high_prior": 55,
            "engineer_null_median_low_prior": 30,
            "engineer_null_median_high_prior": 70,
            "dick_median_both_priors": 50,
            "bat_ball": {"correct": 0.548, "intuitive": 0.402, "other": 0.05, "n": 564},
        },
        "linda": summarize_linda(linda_a_rows, linda_b_rows),
        "engineer_lawyer": summarize_engineer(engineer_rows),
        "bat_ball": summarize_batball(batball_rows),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    plot_linda(summary["linda"], args.output_dir)
    plot_engineer(summary["engineer_lawyer"], args.output_dir)
    plot_batball(summary["bat_ball"], args.output_dir)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
