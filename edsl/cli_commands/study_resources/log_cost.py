#!/usr/bin/env python3
"""Append-only cost ledger for EP-Agent study runs.

Importable:
    from log_cost import log_cost
    log_cost(study_path=".", estimated_cost=5.0, actual_cost=0.89, ...)

CLI:
    python log_cost.py --study-root . --estimated 5.00 --actual 0.89 \
        --agents 18 --questions 12 --model gpt-5.4 --description "pitbull risk"
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def log_cost(
    study_path: str,
    estimated_cost: float,
    actual_cost: float,
    n_agents: int,
    n_questions: int,
    model_name: str,
    description: str = "",
) -> dict:
    """Append one cost record to <study_path>/costs.jsonl and return it."""
    study = Path(study_path).resolve()
    # Derive a short study label from the last two path components
    # e.g. ".../topic_pitbull-risk-perception/study_a" -> "topic_pitbull-risk-perception/study_a"
    label = "/".join(study.parts[-2:]) if len(study.parts) >= 2 else study.name

    ratio = round(estimated_cost / actual_cost, 2) if actual_cost > 0 else None

    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "study": label,
        "estimated_cost_usd": round(estimated_cost, 4),
        "actual_cost_usd": round(actual_cost, 4),
        "n_agents": n_agents,
        "n_questions": n_questions,
        "model": model_name,
        "description": description,
        "ratio": ratio,
    }

    ledger = study / "costs.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a") as f:
        f.write(json.dumps(record) + "\n")

    print(f"Logged ${actual_cost:.4f} (est ${estimated_cost:.4f}, ratio {ratio}) -> {ledger}")
    return record


def main():
    parser = argparse.ArgumentParser(description="Log study run cost to costs.jsonl")
    parser.add_argument("--study-root", required=True, help="Path to study directory")
    parser.add_argument("--estimated", required=True, type=float, help="Estimated cost USD")
    parser.add_argument("--actual", required=True, type=float, help="Actual cost USD")
    parser.add_argument("--agents", required=True, type=int, help="Number of agents")
    parser.add_argument("--questions", required=True, type=int, help="Number of questions")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--description", default="", help="Optional job description")
    args = parser.parse_args()

    log_cost(
        study_path=args.study_root,
        estimated_cost=args.estimated,
        actual_cost=args.actual,
        n_agents=args.agents,
        n_questions=args.questions,
        model_name=args.model,
        description=args.description,
    )


if __name__ == "__main__":
    main()

