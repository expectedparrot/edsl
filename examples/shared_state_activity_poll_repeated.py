"""Run the conformist shared-state activity poll repeatedly.

The experiment keeps the distribution of initial activity preferences balanced.
What varies is their order and the model's response. With sequential visibility
and conformist personas, early votes can generate different informational cascades.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from shared_state_activity_poll import ACTIVITIES, participants, run


def summarize_run(
    results, counts: Counter, run_number: int, seed: int
) -> dict[str, Any]:
    events = results.shared_state["bindings"][0]["events"]
    writes = [event for event in events if event["kind"] == "write"]
    traits = {agent.name: agent.traits for agent in participants(seed=seed)}
    maximum = max(counts.values())
    winners = sorted(activity for activity, count in counts.items() if count == maximum)
    sequence = []
    for event in writes:
        voter = event["inputs"]["voter"]
        choice = event["inputs"]["activity"]
        persona = traits[voter]
        sequence.append(
            {
                "version": event["version"],
                "voter": voter,
                "preferred_activity": persona["preferred_activity"],
                "preference_strength": persona["preference_strength"],
                "conformity": persona["conformity"],
                "choice": choice,
                "followed_preference": choice == persona["preferred_activity"],
            }
        )
    return {
        "run": run_number,
        "seed": seed,
        "counts": {activity: counts.get(activity, 0) for activity in ACTIVITIES},
        "winners": winners,
        "winning_count": maximum,
        "first_three_votes": [item["choice"] for item in sequence[:3]],
        "vote_sequence": sequence,
    }


def run_repetitions(
    repetitions: int = 10,
    *,
    n: int = 16,
    seed: int = 731,
    model_name: str = "gemini-2.5-flash",
    max_concurrency: int = 5,
) -> dict[str, Any]:
    runs = []
    for offset in range(repetitions):
        run_number = offset + 1
        run_seed = seed + offset
        results, counts = run(
            n=n,
            seed=run_seed,
            model_name=model_name,
            max_concurrency=max_concurrency,
            state_id=f"weekend-activity-poll-run-{run_number:02d}",
        )
        summary = summarize_run(results, counts, run_number, run_seed)
        runs.append(summary)
        winners = ", ".join(summary["winners"])
        print(
            f"Run {run_number:02d}: winner={winners}; "
            f"counts={summary['counts']}; "
            f"first_three={summary['first_three_votes']}",
            flush=True,
        )

    winner_frequency = Counter(
        winner for summary in runs for winner in summary["winners"]
    )
    return {
        "experiment": "conformist shared-state activity poll",
        "repetitions": repetitions,
        "participants_per_run": n,
        "base_seed": seed,
        "model": model_name,
        "winner_frequency": {
            activity: winner_frequency.get(activity, 0) for activity in ACTIVITIES
        },
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--participants", type=int, default=16)
    parser.add_argument("--seed", type=int, default=731)
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--max-concurrency", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("shared-state-activity-poll-repeated.json"),
    )
    args = parser.parse_args()
    summary = run_repetitions(
        args.runs,
        n=args.participants,
        seed=args.seed,
        model_name=args.model,
        max_concurrency=args.max_concurrency,
    )
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Winner frequency: {summary['winner_frequency']}")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
