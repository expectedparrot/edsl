"""Tests for the routable, display-only SurveyMessage question type."""

import pytest

from edsl import Model, Survey, SurveyMessage
from edsl.questions import QuestionBase
from edsl.questions.exceptions import QuestionAnswerValidationError


def test_construction_and_serialization_round_trip():
    message = SurveyMessage(
        question_name="thanks",
        question_text="Thank you for completing the survey.",
    )

    assert message.question_type == "survey_message"
    assert message.to_dict()["question_type"] == "survey_message"
    assert QuestionBase.from_dict(message.to_dict()) == message


def test_custom_prompt_configuration_round_trips():
    message = SurveyMessage(
        question_name="notice",
        question_text="Please continue.",
        question_presentation="Custom presentation: {{ question_text }}",
        answering_instructions="Custom instructions",
    )

    restored = QuestionBase.from_dict(message.to_dict())
    assert restored.question_presentation == message.question_presentation
    assert restored.answering_instructions == message.answering_instructions


def test_response_is_deterministic_and_strict():
    message = SurveyMessage(question_name="notice", question_text="Please continue.")

    assert message._validate_answer({"answer": "continued"})["answer"] == "continued"
    assert message._simulate_answer()["answer"] == "continued"
    with pytest.raises(QuestionAnswerValidationError):
        message._validate_answer({"answer": "skip"})


def test_run_records_answer_without_calling_model():
    calls = 0

    def model_response(user_prompt, system_prompt, files_list):
        nonlocal calls
        calls += 1
        return "This should never be called"

    message = SurveyMessage(question_name="notice", question_text="Please continue.")
    results = (
        Survey([message])
        .by(Model("test", func=model_response))
        .run(
            disable_remote_inference=True,
            cache=False,
        )
    )

    assert calls == 0
    assert results.select("answer.notice").first() == "continued"


def test_rules_target_message_with_normal_question_index():
    from edsl import EndOfSurvey
    from edsl.questions import QuestionFreeText

    eligible = QuestionFreeText(
        question_name="eligible", question_text="Are you eligible?"
    )
    follow_up = QuestionFreeText(
        question_name="follow_up", question_text="Tell us more."
    )
    ineligible = SurveyMessage(
        question_name="ineligible",
        question_text="Sorry, you are not eligible for this survey.",
    )
    survey = Survey([eligible, follow_up, ineligible])
    survey.add_rule(
        "eligible", "{{ eligible.answer }} == 'No'", next_question="ineligible"
    )

    assert survey.question_name_to_index["ineligible"] == 2
    assert survey.next_question("eligible", {"eligible.answer": "No"}) is ineligible
    assert survey.next_question(ineligible, {}) is EndOfSurvey


def test_message_advances_to_following_question():
    from edsl.questions import QuestionFreeText

    message = SurveyMessage(question_name="notice", question_text="Please continue.")
    follow_up = QuestionFreeText(
        question_name="follow_up", question_text="Tell us more."
    )
    survey = Survey([message, follow_up])

    assert survey.next_question(message, {}) is follow_up
