#!/usr/bin/env python3
"""Build standard plots from a bounded ``ep results review`` artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_standard_plots.py REPORT_DATA OUTPUT_DIR")
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    review = payload.get("data", payload)
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)

    numeric = review.get("numeric_summaries", [])
    if numeric:
        labels = [item["column"].removeprefix("answer.").replace("_", " ") for item in numeric]
        means = [item["mean"] for item in numeric]
        fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), 4.5))
        bars = ax.bar(labels, means, color="#315b7d")
        ax.bar_label(bars, fmt="%.2f", padding=3)
        ax.set_ylabel("Mean response")
        ax.set_title("Mean numeric responses")
        ax.spines[["top", "right"]].set_visible(False)
        plt.xticks(rotation=25, ha="right")
        fig.tight_layout()
        fig.savefig(output / "standard-rating-means.png", dpi=160)
        plt.close(fig)

    segments = review.get("segment_summaries", [])
    if segments and numeric:
        segment = segments[0]
        column = numeric[0]["column"]
        groups = [g for g in segment.get("groups", []) if column in g.get("means", {})]
        if groups:
            fig, ax = plt.subplots(figsize=(max(6, len(groups) * 1.2), 4.5))
            bars = ax.bar(
                [group["value"] for group in groups],
                [group["means"][column] for group in groups],
                color="#5f8f76",
            )
            ax.bar_label(bars, fmt="%.2f", padding=3)
            ax.set_ylabel(column.removeprefix("answer.").replace("_", " ").title())
            group_name = segment["group_by"].split(".")[-1].replace("_", " ")
            ax.set_title(f"Response by {group_name}")
            ax.spines[["top", "right"]].set_visible(False)
            plt.xticks(rotation=25, ha="right")
            fig.tight_layout()
            fig.savefig(output / "standard-segment-means.png", dpi=160)
            plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

