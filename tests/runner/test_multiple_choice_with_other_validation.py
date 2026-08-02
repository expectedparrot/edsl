"""Local runner regression for structured multiple-choice-with-other output."""

import json

from edsl import Model, QuestionMultipleChoiceWithOther


def test_long_listed_option_in_structured_response_runs_locally():
    long_option = (
        "We share full postback data with only the attributed network and "
        "limited/partial postback data with the other non-attributed networks"
    )
    question = QuestionMultipleChoiceWithOther(
        question_name="q19b_postback_policy",
        question_text="How do you share postback data?",
        question_options=[
            "We do not share postback data with ad networks",
            "We share full postback data with the attributed ad network only",
            "We share full postback data with all ad networks",
            long_option,
            "Not sure",
        ],
        other_option_text="Other (please specify)",
    )
    model = Model("test", canned_response=json.dumps({"answer": long_option}))

    results = question.by(model).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
    )

    assert results.select("answer.q19b_postback_policy").to_list() == [long_option]

