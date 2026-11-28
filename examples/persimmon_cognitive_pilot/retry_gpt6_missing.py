"""Retry only missing GPT-6.2-Sol responses, preserving original option order."""

from __future__ import annotations

import json
import time
from pathlib import Path

from edsl import AgentList, Model, Results, Survey
from edsl.caching import Cache

from run_counterbalanced import make_question, options_with_correct_position
from run_gpt6_comparison import GPT_RESULTS
from run_pilot import ITEMS, make_agents


def main() -> None:
    agents = make_agents()
    item = next(item for item in ITEMS if item["name"] == "occupation_base_rate")
    original_path = GPT_RESULTS / f"{item['name']}.ep"
    original = Results.git.load(original_path)
    prior_rows = original.select(
        "agent.agent_name", f"answer.{item['name']}"
    ).to_list()
    missing_names = [name for name, answer in prior_rows if answer is None]
    if not missing_names:
        print(json.dumps({"retried": 0, "message": "No missing answers."}))
        return

    agent_by_name = {agent.name: agent for agent in agents}
    parts = []
    for agent_index, name in enumerate(agent.name for agent in agents):
        if name not in missing_names:
            continue
        position = agent_index % len(item["options"])
        question = make_question(
            item, options_with_correct_position(item, position)
        )
        result = None
        answer = None
        for retry_index in range(3):
            if retry_index:
                time.sleep(2 ** (retry_index - 1))
            result = Survey([question]).by(
                AgentList([agent_by_name[name]])
            ).by(Model("gpt-6.2-sol", service_name="openai", max_tokens=128)).run(
                cache=Cache(),
                disable_remote_inference=True,
                disable_remote_cache=True,
                max_concurrency=1,
            )
            answer = result.select(f"answer.{item['name']}").to_list()[0]
            if answer is not None:
                break
        parts.append(result)

    retry_results = parts[0]
    for other in parts[1:]:
        retry_results.extend(other)
        retry_results.task_history.total_interviews.extend(
            other.task_history.total_interviews
        )
    retry_path = GPT_RESULTS / f"{item['name']}_retry.ep"
    retry_results.save(str(retry_path))
    print(
        json.dumps(
            {
                "retried_personas": missing_names,
                "retry_answers": retry_results.select(
                    "agent.agent_name", f"answer.{item['name']}"
                ).to_list(),
                "retry_results_file": str(retry_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
