"""Summarize counterbalanced EDSL exports without rerunning inference."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from run_counterbalanced import options_with_correct_position
from run_pilot import ITEMS, ROOT, make_agents


def main() -> None:
    analysis_dir = ROOT / "analysis"
    summary = json.loads(
        (analysis_dir / "summary_counterbalanced.json").read_text(encoding="utf-8")
    )
    agent_index = {agent.name: i for i, agent in enumerate(make_agents())}

    for item_summary in summary["items"]:
        item = next(item for item in ITEMS if item["name"] == item_summary["name"])
        answer_column = f"answer.{item['name']}"
        csv_path = analysis_dir / f"counterbalanced_{item['name']}.csv"
        with csv_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        selected_position_counts = Counter()
        accuracy_by_correct_position = defaultdict(lambda: {"n": 0, "correct_n": 0})
        for row in rows:
            name = row["agent.agent_name"]
            answer = row[answer_column]
            index = agent_index[name]
            correct_position = index % len(item["options"])
            ordered_options = options_with_correct_position(item, correct_position)
            position_key = str(correct_position + 1)
            accuracy_by_correct_position[position_key]["n"] += 1
            if answer == item["correct"]:
                accuracy_by_correct_position[position_key]["correct_n"] += 1
            if answer in ordered_options:
                selected_position_counts[str(ordered_options.index(answer) + 1)] += 1
            else:
                selected_position_counts["<missing-or-invalid>"] += 1

        item_summary["selected_option_position_counts"] = dict(
            selected_position_counts
        )
        item_summary["accuracy_by_correct_option_position"] = dict(
            accuracy_by_correct_position
        )

    out = analysis_dir / "summary_counterbalanced.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
