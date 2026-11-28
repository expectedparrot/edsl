"""Check the saved study package for expected rows, models, and answers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from edsl import Results


EXPECTED_ROWS = 1200
EXPECTED_MODEL_ROWS = 600
EXPECTED_MODELS = {"persimmon-v0.1", "gpt-6.2-sol"}
REQUIRED_ANSWERS = {
    "answer.linda_choice",
    "answer.jack_probability",
    "answer.dick_probability",
    "answer.null_probability",
    "answer.bat_ball_answer",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_path", type=Path)
    args = parser.parse_args()

    results = Results.load(str(args.results_path))
    model_rows = results.select("model.model", "model.inference_service").to_list()
    model_counts = Counter(str(row[0]) for row in model_rows)
    available_columns = set(results.columns)
    missing_columns = sorted(REQUIRED_ANSWERS - available_columns)

    summary = {
        "rows": len(results),
        "model_counts": dict(model_counts),
        "missing_answer_columns": missing_columns,
        "expected_rows": EXPECTED_ROWS,
        "expected_rows_per_model": EXPECTED_MODEL_ROWS,
    }
    output = args.results_path.parent / "qa-summary.json"
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    problems = []
    if len(results) != EXPECTED_ROWS:
        problems.append(f"expected {EXPECTED_ROWS} rows, found {len(results)}")
    if set(model_counts) != EXPECTED_MODELS:
        problems.append(f"expected models {sorted(EXPECTED_MODELS)}, found {sorted(model_counts)}")
    if any(count != EXPECTED_MODEL_ROWS for count in model_counts.values()):
        problems.append(f"expected {EXPECTED_MODEL_ROWS} rows per model, found {dict(model_counts)}")
    if missing_columns:
        problems.append(f"missing answer columns: {', '.join(missing_columns)}")
    if problems:
        raise SystemExit("; ".join(problems))

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
