from edsl import QuestionMultipleChoice, QuestionNumerical, Scenario


def test_multiple_choice_question_options_format():
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


def test_multiple_choice_question_options_format_with_nested_scenario():
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


def test_numerical_question_min_max_format():
    # Create the multiple choice question
    q = QuestionNumerical(
        question_name="age",
        question_text="How old are you?",
        min_value="{{ scenario.min_age }}",
        max_value="{{ scenario.max_age }}",
    )

    # Create the nested scenario with options
    s = Scenario({"min_age": 20, "max_age": 100})

    # Get the prompt
    actual_prompt = q.by(s).prompts().select("user_prompt").first().text

    # Define the expected prompt format

    # Assert that the actual prompt matches the expected prompt
    assert "20" in actual_prompt
    assert "100" in actual_prompt


def test_numerical_question_min_max_format_with_nested_scenario():
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
