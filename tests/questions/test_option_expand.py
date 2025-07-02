from edsl import QuestionMultipleChoice, Scenario


def test_multiple_choice_question_format():
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


def test_multiple_choice_question_format_with_nested_scenario():
    # Create the multiple choice question
    q = QuestionMultipleChoice(
        question_name="capital_of_france",
        question_text="What is the capital of France?",
        question_options="{{ scenario.cities['choices'] }}",
    )

    # Create the nested scenario with options
    s = Scenario({"cities": {"choices": ["Paris", "London", "Berlin", "Madrid"]}})

    # Get the prompt
    actual_prompt = q.by(s).prompts().select("user_prompt").first().text

    # Define the expected prompt format

    # Assert that the actual prompt matches the expected prompt
    assert "Paris" in actual_prompt
    assert "London" in actual_prompt
    assert "Berlin" in actual_prompt
    assert "Madrid" in actual_prompt
