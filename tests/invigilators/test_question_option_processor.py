from types import SimpleNamespace

from edsl import Scenario
from edsl.invigilators.question_option_processor import QuestionOptionProcessor


def test_renders_comment_template_in_individual_option():
    prior_answers = {
        "q1": SimpleNamespace(answer="Yes", comment="Because it is useful")
    }
    processor = QuestionOptionProcessor(Scenario({}), prior_answers)

    options = processor.get_question_options(
        {"question_options": ["{{ q1.comment }}", "No comment"]}
    )

    assert options == ["Because it is useful", "No comment"]


def test_renders_multiple_prior_answers_in_individual_options():
    prior_answers = {
        "q1": SimpleNamespace(answer="apple", comment=None),
        "q2": SimpleNamespace(answer="pear", comment=None),
    }
    processor = QuestionOptionProcessor(Scenario({}), prior_answers)

    options = processor.get_question_options(
        {
            "question_options": [
                "{{ q1.answer }}",
                "blueberry",
                "{{ q2.answer }}",
            ]
        }
    )

    assert options == ["apple", "blueberry", "pear"]


def test_preserves_native_values_in_option_list():
    processor = QuestionOptionProcessor(
        Scenario({"rank": 2}),
        {"q1": SimpleNamespace(answer=None, comment=None)},
    )

    options = processor.get_question_options(
        {
            "question_options": [
                "{{ scenario.rank }}",
                "{{ q1.answer }}",
                3,
            ]
        }
    )

    assert options == [2, None, 3]


def test_renders_templates_in_additional_options():
    prior_answers = {
        "q1": SimpleNamespace(answer=["apple", "pear"], comment="Other fruit")
    }
    processor = QuestionOptionProcessor(Scenario({}), prior_answers)

    options = processor.get_question_options(
        {
            "question_options": {
                "from": "{{ q1.answer }}",
                "add": ["{{ q1.comment }}", "None"],
            }
        }
    )

    assert options == ["apple", "pear", "Other fruit", "None"]


def test_preserves_malformed_template_in_individual_option():
    processor = QuestionOptionProcessor(Scenario({}), {})

    options = processor.get_question_options(
        {"question_options": ["Use {{name", "Other"]}
    )

    assert options == ["Use {{name", "Other"]


def test_preserves_malformed_template_in_additional_option():
    prior_answers = {"q1": SimpleNamespace(answer=["apple", "pear"], comment=None)}
    processor = QuestionOptionProcessor(Scenario({}), prior_answers)

    options = processor.get_question_options(
        {
            "question_options": {
                "from": "{{ q1.answer }}",
                "add": ["Use {{name"],
            }
        }
    )

    assert options == ["apple", "pear", "Use {{name"]
