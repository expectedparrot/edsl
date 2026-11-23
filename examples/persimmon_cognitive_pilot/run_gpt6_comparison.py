"""Run the counterbalanced judgment items with GPT-6.2-Sol for comparison."""

from __future__ import annotations

import json
import time
from collections import Counter

from edsl import Model, Results, Survey
from edsl.caching import Cache

from run_counterbalanced import (
    ANALYSIS,
    RESULTS,
    make_question,
    options_with_correct_position,
)
from run_pilot import ITEMS, ROOT, make_agents


MODEL_NAME = "gpt-6.2-sol"
GPT_RESULTS = RESULTS / "gpt-6.2-sol"
PERSIMMON_RESULTS = RESULTS


def main() -> None:
    GPT_RESULTS.mkdir(parents=True, exist_ok=True)
    agents = make_agents()
    model = Model(MODEL_NAME, service_name="openai", max_tokens=128)
    summary = {
        "model": MODEL_NAME,
        "service": "openai",
        "persona_count": len(agents),
        "position_design": "same counterbalanced position assignment as Persimmon run",
        "items": [],
    }

    for item in ITEMS:
        result_path = GPT_RESULTS / f"{item['name']}.ep"
        position_counts = Counter()
        for index in range(len(agents)):
            correct_position = index % len(item["options"])
            position_counts[str(correct_position + 1)] += 1
        if result_path.exists():
            combined = Results.git.load(result_path)
        else:
            parts = []
            for index, agent in enumerate(agents):
                correct_position = index % len(item["options"])
                options = options_with_correct_position(item, correct_position)
                question = make_question(item, options)
                result = Survey([question]).by(agent).by(model).run(
                    cache=Cache(),
                    disable_remote_inference=True,
                    disable_remote_cache=True,
                    max_concurrency=1,
                )
                answer = result.select(f"answer.{item['name']}").to_list()[0]
                if answer is None:
                    for retry_index in range(2):
                        time.sleep(2**retry_index)
                        result = Survey([question]).by(agent).by(model).run(
                            cache=Cache(),
                            disable_remote_inference=True,
                            disable_remote_cache=True,
                            max_concurrency=1,
                        )
                        answer = result.select(
                            f"answer.{item['name']}"
                        ).to_list()[0]
                        if answer is not None:
                            break
                parts.append(result)

            combined = parts[0]
            for other in parts[1:]:
                combined.extend(other)
                combined.task_history.total_interviews.extend(
                    other.task_history.total_interviews
                )
            combined.save(str(result_path))
        rows = combined.select(
            "agent.agent_name", f"answer.{item['name']}"
        ).to_list()
        answers = Counter(
            str(answer) if answer is not None else "<missing>"
            for _agent_name, answer in rows
        )

        persimmon_path = PERSIMMON_RESULTS / f"{item['name']}.ep"
        persimmon_rows = Results.git.load(persimmon_path).select(
            "agent.agent_name", f"answer.{item['name']}"
        ).to_list()
        persimmon_answers = {
            name: answer for name, answer in persimmon_rows
        }
        gpt_answers = {name: answer for name, answer in rows}
        paired = sum(
            gpt_answers.get(name) == persimmon_answers.get(name)
            for name in persimmon_answers
        )
        valid_n = sum(answer is not None for _name, answer in rows)
        summary["items"].append(
            {
                "name": item["name"],
                "concept": item["concept"],
                "correct_option": item["correct"],
                "n": len(rows),
                "valid_n": valid_n,
                "correct_n": sum(answer == item["correct"] for _name, answer in rows),
                "answer_counts": dict(answers),
                "correct_option_position_counts": dict(position_counts),
                "same_answer_as_persimmon_n": paired,
                "results_file": str(result_path.relative_to(ROOT)),
            }
        )

    summary_path = ANALYSIS / "summary_gpt6_comparison.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
