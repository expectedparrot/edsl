from edsl.language_models.model import Model
from edsl.questions import (
    QuestionMultipleChoice,
    QuestionNumerical,
)
from edsl.scenarios import Scenario
from edsl.surveys import Survey


def test_multiple_choice_options_from_scenario():
    # Create the multiple choice question
    q = QuestionMultipleChoice(
        question_name="capital_of_france",
        question_text="What is the capital of France?",
        question_options="{{ scenario.question_options }}",
    )

    # Create the scenario with options
    s = Scenario({"question_options": ["Paris", "London", "Berlin", "Madrid"]})

    # Get the prompt
    actual_prompt = q.by(s).prompts().select("user_prompt").first().text

    # Define the expected prompt format

    # Assert that the actual prompt matches the expected prompt
    assert "Paris" in actual_prompt
    assert "London" in actual_prompt
    assert "Berlin" in actual_prompt
    assert "Madrid" in actual_prompt


def test_multiple_choice_options_from_nested_scenario():
    # Create the multiple choice question
    q = QuestionMultipleChoice(
        question_name="capital_of_france",
        question_text="What is the capital of France?",
        question_options="{{ scenario.cities[0]['choices'] }}",
    )

    # Create the nested scenario with options
    s = Scenario({"cities": [{"choices": ["Paris", "London", "Berlin", "Madrid"]}]})

    # Get the prompt
    actual_prompt = q.by(s).prompts().select("user_prompt").first().text

    # Define the expected prompt format

    # Assert that the actual prompt matches the expected prompt
    assert "Paris" in actual_prompt
    assert "London" in actual_prompt
    assert "Berlin" in actual_prompt
    assert "Madrid" in actual_prompt


def test_checkbox_options_from_prior_answers():
    from edsl.questions import QuestionList, QuestionCheckBox

    def two_responses_closure():

        num_calls = 0

        def two_responses(user_prompt, system_prompt, files_list):
            nonlocal num_calls
            if num_calls == 0:
                num_calls += 1
                return """["Red", "Blue", "Green", "Yellow", "Orange"]"""
            else:
                return "Red, Blue, Yellow"

        return two_responses

    m = Model("test", func=two_responses_closure())

    q1 = QuestionList(question_name="colors", question_text="Draft a list of colors.")

    q2 = QuestionCheckBox(
        question_name="primary",
        question_text="Which of these colors are primary?",
        question_options="{{ colors.answer }}",
    )

    survey = Survey([q1, q2])

    results = survey.by(m).run(stop_on_exception=True, disable_remote_inference=True)

    # Confirm it got passed through
    assert results.select("question_options.primary").to_list()[0] == [
        "Red",
        "Blue",
        "Green",
        "Yellow",
        "Orange",
    ]


def test_numerical_min_max_from_scenario():
    # Create the multiple choice question
    q = QuestionNumerical(
        question_name="age",
        question_text="How old are you?",
        min_value="{{ scenario.min_age }}",
        max_value="{{ scenario.max_age }}",
    )

    # Create the scenario with options
    s = Scenario({"min_age": 20, "max_age": 100})

    # Get the prompt
    actual_prompt = q.by(s).prompts().select("user_prompt").first().text

    # Define the expected prompt format

    # Assert that the actual prompt matches the expected prompt
    assert "20" in actual_prompt
    assert "100" in actual_prompt


def test_numerical_min_max_from_nested_scenario():
    # Create the multiple choice question
    q = QuestionNumerical(
        question_name="age",
        question_text="How old are you?",
        min_value="{{ scenario.age_range['min'] }}",
        max_value="{{ scenario.age_range['max'] }}",
    )

    # Create the nested scenario with options
    s = Scenario({"age_range": {"min": 20, "max": 100}})

    # Get the prompt
    actual_prompt = q.by(s).prompts().select("user_prompt").first().text

    # Define the expected prompt format

    # Assert that the actual prompt matches the expected prompt
    assert "20" in actual_prompt
    assert "100" in actual_prompt


def test_numerical_min_from_prior_answers():
    def two_responses_closure():

        num_calls = 0

        def two_responses(user_prompt, system_prompt, files_list):
            nonlocal num_calls
            if num_calls == 0:
                num_calls += 1
                return """12"""
            else:
                return """36"""

        return two_responses

    m = Model("test", func=two_responses_closure())

    q1 = QuestionMultipleChoice(
        question_name="eggs_in_dozen",
        question_text="How many eggs are in a dozen?",
        question_options=[6, 10, 12, 24],
    )

    q2 = QuestionNumerical(
        question_name="eggs_in_three_dozen",
        question_text="How many eggs are in three dozen?",
        min_value="{{ eggs_in_dozen.answer }}",
    )

    survey = Survey([q1, q2])

    results = survey.by(m).run(stop_on_exception=True, disable_remote_inference=True)

    # Confirm it got passed through
    assert (
        "Minimum answer value: 12"
        in results.select("prompt.eggs_in_three_dozen_user_prompt").first().text
    )
