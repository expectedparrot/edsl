"""Compare saved Persimmon and GPT-6.2-Sol responses on common support."""

from __future__ import annotations

import json
from collections import Counter

from edsl import Results

from run_gpt6_comparison import GPT_RESULTS, PERSIMMON_RESULTS
from run_pilot import ITEMS, make_agents


ROOT = GPT_RESULTS.parents[2]
ANALYSIS = ROOT / "analysis"


def rows_by_agent(path, question_name):
    results = Results.git.load(path)
    return {
        name: answer
        for name, answer in results.select(
            "agent.agent_name", f"answer.{question_name}"
        ).to_list()
    }


def main() -> None:
    agent_names = [agent.name for agent in make_agents()]
    summary = {
        "models": ["persimmon-v0.1", "gpt-6.2-sol"],
        "comparison_basis": "same 12 personas, wording, and deterministic option-position schedule; paired valid-response intersection",
        "items": [],
    }

    for item in ITEMS:
        name = item["name"]
        persimmon = rows_by_agent(PERSIMMON_RESULTS / f"{name}.ep", name)
        gpt = rows_by_agent(GPT_RESULTS / f"{name}.ep", name)
        retry_path = GPT_RESULTS / f"{name}_retry.ep"
        if retry_path.exists():
            gpt.update(
                {
                    agent_name: answer
                    for agent_name, answer in rows_by_agent(retry_path, name).items()
                    if answer is not None
                }
            )

        common = [
            agent_name
            for agent_name in agent_names
            if persimmon.get(agent_name) is not None
            and gpt.get(agent_name) is not None
        ]
        gpt_valid = [name for name in agent_names if gpt.get(name) is not None]
        pers_valid = [name for name in agent_names if persimmon.get(name) is not None]

        def distribution(answer_map, names):
            return dict(Counter(str(answer_map[agent_name]) for agent_name in names))

        positions = {
            agent_name: index % len(item["options"])
            for index, agent_name in enumerate(agent_names)
        }
        correct_position_counts = Counter(
            str(positions[name] + 1) for name in agent_names
        )
        gpt_position_choices = Counter()
        # Reconstruct the deterministic rotation used by the runner.
        for agent_name in gpt_valid:
            correct_position = positions[agent_name]
            distractors = [
                option for option in item["options"] if option != item["correct"]
            ]
            options = list(distractors)
            options.insert(correct_position, item["correct"])
            gpt_position_choices[str(options.index(gpt[agent_name]) + 1)] += 1

        summary["items"].append(
            {
                "name": name,
                "concept": item["concept"],
                "correct_option": item["correct"],
                "persimmon_valid_n": len(pers_valid),
                "gpt6_valid_n": len(gpt_valid),
                "common_support_n": len(common),
                "persimmon_answer_counts": distribution(persimmon, pers_valid),
                "gpt6_answer_counts": distribution(gpt, gpt_valid),
                "persimmon_correct_on_common": sum(
                    persimmon[agent_name] == item["correct"] for agent_name in common
                ),
                "gpt6_correct_on_common": sum(
                    gpt[agent_name] == item["correct"] for agent_name in common
                ),
                "same_answer_on_common": sum(
                    persimmon[agent_name] == gpt[agent_name] for agent_name in common
                ),
                "correct_option_position_counts": dict(correct_position_counts),
                "gpt6_selected_position_counts": dict(gpt_position_choices),
            }
        )

    summary_path = ANALYSIS / "summary_model_comparison.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
