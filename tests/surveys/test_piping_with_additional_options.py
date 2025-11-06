"""Test case for GitHub issue #2308: Adding options to piped question options"""
import pytest
from edsl.questions import QuestionList, QuestionMultipleChoice
from edsl.surveys import Survey
from edsl.agents import Agent
from edsl.language_models import LanguageModel


def test_piping_with_additional_static_options():
    """
    Test that we can pipe options from a prior answer AND add additional static options.
    This addresses GitHub issue #2308.

    Use case: User answers q1 with a list, then q2 should have those options PLUS "None of the above"
    """
    a = Agent()
    m = LanguageModel.example(test_model=True)

    def f(self, question, scenario):
        if question.question_name == "q1":
            return ["Option A", "Option B", "Option C"]
        if question.question_name == "q2":
            return "Option A"

    a.add_direct_question_answering_method(f)

    # Create questions
    q1 = QuestionList(
        question_name="q1",
        question_text="What are your favorite options?",
        max_list_items=5,
    )

    # q2 should have the options from q1 PLUS additional static options
    # Using dict syntax: {"from": "{{ q1.answer }}", "add": ["None of the above"]}
    q2 = QuestionMultipleChoice(
        question_name="q2",
        question_text="Which one is your top choice?",
        question_options={
            "from": "{{ q1.answer }}",
            "add": ["None of the above", "Other"]
        }
    )

    survey = Survey([q1, q2])

    # Run the survey
    results = survey.by(a).by(m).run(disable_remote_inference=True)

    # Check that q2 has all the options from q1 plus the additional options
    q2_options = results.select("question_options.q2_question_options").first()

    expected_options = ['Option A', 'Option B', 'Option C', 'None of the above', 'Other']
    assert set(q2_options) == set(expected_options), f"Expected {expected_options}, got {q2_options}"


def test_piping_from_scenario_with_additional_options():
    """
    Test piping options from scenario data with additional static options.
    """
    from edsl import Scenario

    a = Agent()
    m = LanguageModel.example(test_model=True)

    def f(self, question, scenario):
        if question.question_name == "q1":
            return "Red"

    a.add_direct_question_answering_method(f)

    # Create a scenario with options
    scenario = Scenario({"colors": ["Red", "Blue", "Green"]})

    # Create question that pipes from scenario and adds options
    q1 = QuestionMultipleChoice(
        question_name="q1",
        question_text="What's your favorite color?",
        question_options={
            "from": "{{ scenario.colors }}",
            "add": ["Other", "None"]
        }
    )

    survey = Survey([q1])
    results = survey.by(scenario).by(a).by(m).run(disable_remote_inference=True)

    # Check that q1 has all options
    q1_options = results.select("question_options.q1_question_options").first()
    expected_options = ['Red', 'Blue', 'Green', 'Other', 'None']

    assert set(q1_options) == set(expected_options), f"Expected {expected_options}, got {q1_options}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
