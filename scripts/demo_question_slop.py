"""Demonstrate QuestionSlop with Pangram local inference.

Run from the repo root:

    python scripts/demo_question_slop.py

The script reads PANGRAM_API_KEY from the process environment or from .env.
It uses EDSL local execution via disable_remote_inference=True; Pangram is still
called over the network by QuestionSlop.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

from edsl import Model, QuestionSlop, ScenarioList


DEFAULT_TEXTS = [
    (
        "This is a short demonstration of QuestionSlop. It sends rendered text "
        "to Pangram and returns normalized detector metrics in EDSL Results."
    )
]


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE lines without adding a dependency."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def compact_score(answer: dict) -> dict:
    return {
        "classification": answer.get("classification"),
        "headline": answer.get("headline"),
        "provider_model": answer.get("provider_model"),
        "ai_score": answer.get("ai_score"),
        "ai_assisted_score": answer.get("ai_assisted_score"),
        "human_score": answer.get("human_score"),
        "text_length": answer.get("text_length"),
        "segments": len(answer.get("segments") or []),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--text",
        action="append",
        help="Text to score. Can be passed more than once.",
    )
    parser.add_argument(
        "--include-segments",
        action="store_true",
        help="Include Pangram window/segment output in the answer.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()

    if not os.environ.get("PANGRAM_API_KEY"):
        raise SystemExit("PANGRAM_API_KEY is not set in the environment or .env")

    texts: Iterable[str] = args.text or DEFAULT_TEXTS
    scenarios = ScenarioList.from_list("text", list(texts))
    question = QuestionSlop(
        question_name="slop",
        question_text="{{ text }}",
        include_segments=args.include_segments,
        include_raw_response=False,
        min_text_length=0,
        timeout_seconds=60,
    )

    results = (
        question.by(scenarios)
        .by(Model("test"))
        .run(disable_remote_inference=True, progress_bar=False, stop_on_exception=True)
    )

    scored_texts = results.select("scenario.text").to_list()
    answers = results.select("answer.slop").to_list()

    for index, (text, answer) in enumerate(zip(scored_texts, answers), start=1):
        print(f"\nExample {index}")
        print(f"Text: {text[:120]}")
        print(f"Score: {compact_score(answer)}")


if __name__ == "__main__":
    main()

