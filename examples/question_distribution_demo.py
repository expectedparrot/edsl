"""Run all three QuestionDistribution forms without making paid model calls.

From an EDSL checkout:
    PYTHONPATH=. python examples/question_distribution_demo.py --output-dir /tmp/distribution-demo

The local test model returns scripted probabilities to demonstrate validation,
execution, and Results storage. Replace it with a real Model to elicit forecasts.
"""

import argparse
import json
from pathlib import Path

from edsl import Model, QuestionDistribution
from edsl.questions.exceptions import QuestionCreationValidationError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("distribution-demo-results")
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cases = [
        (
            QuestionDistribution(
                "winner", "Which candidate will win?", question_options=["a", "b", "c"]
            ),
            {"a": 0.2, "b": 0.2, "c": 0.6},
        ),
        (
            QuestionDistribution(
                "wait",
                "How many minutes will the wait be?",
                bins=["[0,10)", "[10, Inf]"],
            ),
            {"[0,10)": 0.2, "[10,Inf)": 0.8},
        ),
        (
            QuestionDistribution(
                "duration",
                "How long will the task take, from 0 to 25 minutes?",
                min_value=0,
                max_value=25,
                bucket_size=10,
            ),
            {"[0,10)": 0.2, "[10,20)": 0.5, "[20,25]": 0.3},
        ),
    ]
    output = {"model": "test (scripted responses; no paid inference)", "examples": []}
    for question, scripted_answer in cases:
        results = question.by(
            Model("test", canned_response=json.dumps(scripted_answer))
        ).run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exception=True,
        )
        answer = results.select(f"answer.{question.question_name}").to_list()[0]
        assert answer == scripted_answer
        path = args.output_dir / f"{question.question_name}.ep"
        results.save(str(path))
        output["examples"].append(
            {
                "question": question.question_name,
                "answer_keys": question.answer_keys,
                "answer": answer,
                "results": str(path),
            }
        )

    try:
        QuestionDistribution("invalid", "Predict.", bins=["[0,10]", "[10,20]"])
    except QuestionCreationValidationError:
        output["construction_check"] = "Rejected overlapping intervals at 10."
    else:
        raise AssertionError("Overlapping intervals should fail before inference.")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
