"""Small, reproducible Persimmon pilot on classic judgment problems."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionMultipleChoice, Survey
from edsl.caching import Cache


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def make_agents() -> AgentList:
    profiles = [
        ("Maya", 29, "nurse", "careful and people-focused"),
        ("Theo", 42, "building supervisor", "practical and direct"),
        ("Lina", 35, "graphic designer", "creative and reflective"),
        ("Andre", 57, "high school teacher", "methodical and patient"),
        ("Priya", 24, "graduate student", "analytical and curious"),
        ("Jordan", 38, "freelance photographer", "spontaneous and observant"),
        ("Rosa", 49, "clinic coordinator", "organized and community-minded"),
        ("Malik", 32, "small business owner", "budget-conscious and decisive"),
        ("Evelyn", 68, "retired librarian", "thoughtful and cautious"),
        ("Chen", 41, "software quality analyst", "systematic and detail-oriented"),
        ("Sam", 27, "restaurant manager", "fast-moving and adaptable"),
        ("Denise", 54, "transit operator", "experienced and skeptical of assumptions"),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={"age": age, "occupation": occupation, "style": style},
                instruction=(
                    f"You are {name}, a fictional person who is {style}. "
                    "Answer the question as you naturally would; do not try to "
                    "guess the experimenter's preferred answer."
                ),
            )
            for name, age, occupation, style in profiles
        ]
    )


ITEMS = [
    {
        "name": "linda_conjunction",
        "concept": "Conjunction judgment",
        "correct": "Linda is a bank teller.",
        "text": (
            "Linda is 31, outspoken, and studied philosophy. At university she "
            "volunteered with social justice groups and joined demonstrations "
            "about nuclear disarmament. Which statement is more likely?"
        ),
        "options": [
            "Linda is a bank teller.",
            "Linda is a bank teller and active in a feminist organization.",
        ],
    },
    {
        "name": "occupation_base_rate",
        "concept": "Representativeness and base rates",
        "correct": "Lawyer",
        "text": (
            "A group contains 70 lawyers and 30 engineers. One person is selected "
            "at random. The person is quiet, enjoys math puzzles, and spends free "
            "time building small gadgets. Which occupation is more likely?"
        ),
        "options": ["Lawyer", "Engineer", "Equally likely"],
    },
    {
        "name": "taxi_bayes",
        "concept": "Base-rate updating",
        "correct": "Blue taxi",
        "text": (
            "In a city, 85% of taxis are blue and 15% are green. A witness to a "
            "night-time collision identifies the taxi as green. Under similar "
            "conditions, the witness identifies taxi colors correctly 80% of the "
            "time. Which color is more likely for the taxi involved?"
        ),
        "options": ["Blue taxi", "Green taxi", "Equally likely"],
    },
    {
        "name": "bat_ball",
        "concept": "Cognitive reflection",
        "correct": "$0.05",
        "text": (
            "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than "
            "the ball. How much does the ball cost?"
        ),
        "options": ["$0.05", "$0.10", "$0.15", "$0.20"],
    },
]


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    agents = make_agents()
    model = Model("persimmon-v0.1", service_name="persimmon", max_tokens=128)
    summary = {
        "model": "persimmon-v0.1",
        "tier": model.parameters.get("tier", "standard"),
        "persona_count": len(agents),
        "items": [],
    }

    for item in ITEMS:
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
        results = Survey([question]).by(agents).by(model).run(
            cache=Cache(),
            disable_remote_inference=True,
            disable_remote_cache=True,
            max_concurrency=2,
        )
        result_path = RESULTS / f"{item['name']}.ep"
        results.save(str(result_path))
        rows = results.select(
            "agent.agent_name", f"answer.{item['name']}"
        ).to_list()
        by_answer = Counter(
            str(answer) if answer is not None else "<missing>"
            for _agent_name, answer in rows
        )
        summary["items"].append(
            {
                "name": item["name"],
                "concept": item["concept"],
                "correct_option": item["correct"],
                "options": item["options"],
                "n": len(rows),
                "valid_n": sum(answer is not None for _name, answer in rows),
                "correct_n": sum(answer == item["correct"] for _name, answer in rows),
                "answer_counts": dict(by_answer),
                "results_file": str(result_path.relative_to(ROOT)),
            }
        )

    analysis_dir = ROOT / "analysis"
    analysis_dir.mkdir(exist_ok=True)
    (analysis_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
