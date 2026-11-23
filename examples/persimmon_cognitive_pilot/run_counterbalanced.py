"""Counterbalanced-position follow-up for the Persimmon judgment pilot."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from edsl import Model, QuestionMultipleChoice, Survey
from edsl.caching import Cache

from run_pilot import ITEMS, ROOT, make_agents


RESULTS = ROOT / "results" / "counterbalanced"
ANALYSIS = ROOT / "analysis"


def options_with_correct_position(item: dict, position: int) -> list[str]:
    distractors = [option for option in item["options"] if option != item["correct"]]
    ordered = list(distractors)
    ordered.insert(position, item["correct"])
    return ordered


def make_question(item: dict, options: list[str]) -> QuestionMultipleChoice:
    return QuestionMultipleChoice(
        question_name=item["name"],
        question_text=item["text"],
        question_options=options,
        include_comment=False,
        answering_instructions=(
            "Choose exactly one option. Return only the exact option text, "
            "with no explanation."
        ),
    )


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    agents = make_agents()
    model = Model("persimmon-v0.1", service_name="persimmon", max_tokens=128)
    summary = {
        "model": "persimmon-v0.1",
        "tier": model.parameters.get("tier", "standard"),
        "persona_count": len(agents),
        "position_design": "correct option rotated evenly across available positions",
        "items": [],
    }

    for item in ITEMS:
        result_parts = []
        position_counts = Counter()
        for index, agent in enumerate(agents):
            correct_position = index % len(item["options"])
            options = options_with_correct_position(item, correct_position)
            position_counts[str(correct_position + 1)] += 1
            question = make_question(item, options)
            results = Survey([question]).by(agent).by(model).run(
                cache=Cache(),
                disable_remote_inference=True,
                disable_remote_cache=True,
                max_concurrency=1,
            )
            result_parts.append(results)

            answer = results.select(f"answer.{item['name']}").to_list()[0]
            if answer is None:
                # A bounded retry handles transient rate limits without rerunning
                # successful respondents or changing their option position.
                for retry_index in range(2):
                    time.sleep(2**retry_index)
                    results = Survey([question]).by(agent).by(model).run(
                        cache=Cache(),
                        disable_remote_inference=True,
                        disable_remote_cache=True,
                        max_concurrency=1,
                    )
                    result_parts[-1] = results
                    answer = results.select(f"answer.{item['name']}").to_list()[0]
                    if answer is not None:
                        break

        combined = result_parts[0]
        for other in result_parts[1:]:
            combined.extend(other)
            combined.task_history.total_interviews.extend(
                other.task_history.total_interviews
            )
        result_path = RESULTS / f"{item['name']}.ep"
        combined.save(str(result_path))

        rows = combined.select(
            "agent.agent_name", f"answer.{item['name']}"
        ).to_list()
        answer_counts = Counter(
            str(answer) if answer is not None else "<missing>"
            for _agent_name, answer in rows
        )
        summary["items"].append(
            {
                "name": item["name"],
                "concept": item["concept"],
                "correct_option": item["correct"],
                "n": len(rows),
                "valid_n": sum(answer is not None for _name, answer in rows),
                "correct_n": sum(answer == item["correct"] for _name, answer in rows),
                "answer_counts": dict(answer_counts),
                "correct_option_position_counts": dict(position_counts),
                "results_file": str(result_path.relative_to(ROOT)),
            }
        )

    summary_path = ANALYSIS / "summary_counterbalanced.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
