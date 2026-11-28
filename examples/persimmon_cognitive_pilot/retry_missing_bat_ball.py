"""Retry only missing bat-and-ball respondents and rebuild the summary by agent."""

from __future__ import annotations

import json
from collections import Counter

from edsl import AgentList, Model, QuestionMultipleChoice, Survey
from edsl.caching import Cache
from edsl.results import Results

from run_pilot import ITEMS, RESULTS, make_agents


def main() -> None:
    original = Results.git.load(RESULTS / "bat_ball.ep")
    prior_rows = original.select(
        "agent.agent_name", "answer.bat_ball"
    ).to_list()
    original_answers = dict(prior_rows)
    missing_names = {
        name for name, answer in prior_rows if answer is None
    }

    retry_paths = sorted(RESULTS.glob("bat_ball_retry*.ep"))
    retry_answers = {}
    attempted_names = set()
    for retry_path in retry_paths:
        retry_results = Results.git.load(retry_path)
        for name, answer in retry_results.select(
            "agent.agent_name", "answer.bat_ball"
        ).to_list():
            attempted_names.add(name)
            if answer is not None:
                retry_answers[name] = answer

    missing_names.difference_update(retry_answers)
    new_retry_rows = []
    if missing_names:
        all_agents = make_agents()
        retry_agents = AgentList(
            [agent for agent in all_agents if agent.name in missing_names]
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
        attempt = 1
        retry_path = RESULTS / f"bat_ball_retry_{attempt:03d}.ep"
        while retry_path.exists():
            attempt += 1
            retry_path = RESULTS / f"bat_ball_retry_{attempt:03d}.ep"
        results.save(str(retry_path))
        retry_paths.append(retry_path)
        new_retry_rows = results.select(
            "agent.agent_name", "answer.bat_ball"
        ).to_list()
        for name, answer in new_retry_rows:
            attempted_names.add(name)
            if answer is not None:
                retry_answers[name] = answer

    answers_by_agent = dict(original_answers)
    answers_by_agent.update(retry_answers)
    summary_path = RESULTS.parent / "analysis" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    item_summary = next(
        item_summary
        for item_summary in summary["items"]
        if item_summary["name"] == "bat_ball"
    )
    item = next(item for item in ITEMS if item["name"] == "bat_ball")
    valid_answers = [answer for answer in answers_by_agent.values() if answer is not None]
    counts = Counter(
        str(answer) if answer is not None else "<missing>"
        for answer in answers_by_agent.values()
    )
    item_summary.update(
        {
            "n": len(answers_by_agent),
            "valid_n": len(valid_answers),
            "correct_n": sum(answer == item["correct"] for answer in valid_answers),
            "answer_counts": dict(counts),
            "retry_n": len(attempted_names),
            "recovered_personas": sorted(retry_answers),
            "retry_results_files": [
                str(path.relative_to(RESULTS.parent)) for path in retry_paths
            ],
        }
    )
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "retried_personas": sorted(name for name, _ in new_retry_rows),
                "retry_answers": new_retry_rows,
                "valid_n_after_retry": item_summary["valid_n"],
                "correct_n_after_retry": item_summary["correct_n"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
