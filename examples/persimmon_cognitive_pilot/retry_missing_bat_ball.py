"""Retry only the rate-limited bat-and-ball respondents from the pilot."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from edsl import AgentList, Model, QuestionMultipleChoice, Survey
from edsl.caching import Cache
from edsl.results import Results

from run_pilot import ITEMS, RESULTS, make_agents


def main() -> None:
    original = Results.git.load(RESULTS / "bat_ball.ep")
    prior_rows = original.select(
        "agent.agent_name", "answer.bat_ball"
    ).to_list()
    missing_names = [name for name, answer in prior_rows if answer is None]
    if not missing_names:
        print(json.dumps({"retried": 0, "message": "No missing answers."}))
        return

    all_agents = make_agents()
    retry_agents = AgentList(
        [agent for agent in all_agents if agent.name in set(missing_names)]
    )
    item = next(item for item in ITEMS if item["name"] == "bat_ball")
    question = QuestionMultipleChoice(
        question_name=item["name"],
        question_text=item["text"],
        question_options=item["options"],
        include_comment=False,
        answering_instructions=(
            "Choose exactly one option. Return only the exact option text, "
            "with no explanation."
        ),
    )
    results = Survey([question]).by(retry_agents).by(
        Model("persimmon-v0.1", service_name="persimmon", max_tokens=128)
    ).run(
        cache=Cache(),
        disable_remote_inference=True,
        disable_remote_cache=True,
        max_concurrency=1,
    )
    retry_path = RESULTS / "bat_ball_retry.ep"
    results.save(str(retry_path))
    retry_rows = results.select(
        "agent.agent_name", "answer.bat_ball"
    ).to_list()

    summary_path = RESULTS.parent / "analysis" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    item_summary = next(
        item_summary
        for item_summary in summary["items"]
        if item_summary["name"] == "bat_ball"
    )
    counts = Counter(
        {
            answer: count
            for answer, count in item_summary["answer_counts"].items()
            if answer != "<missing>"
        }
    )
    for _name, answer in retry_rows:
        if answer is not None:
            counts[str(answer)] += 1
    item_summary["answer_counts"] = dict(counts)
    item_summary["valid_n"] += sum(answer is not None for _name, answer in retry_rows)
    item_summary["correct_n"] += sum(
        answer == item["correct"] for _name, answer in retry_rows
    )
    item_summary["retry_n"] = len(retry_rows)
    item_summary["recovered_personas"] = [name for name, _answer in retry_rows]
    item_summary["retry_results_file"] = str(retry_path.relative_to(RESULTS.parent))
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "retried_personas": missing_names,
                "retry_answers": retry_rows,
                "valid_n_after_retry": item_summary["valid_n"],
                "correct_n_after_retry": item_summary["correct_n"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
