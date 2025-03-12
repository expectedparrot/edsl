import pytest

def test_scenario_loop_no_exceptions():
    """Test that the scenario loop code runs without throwing exceptions."""
    try:
        from edsl import ScenarioList, QuestionLinearScale

        scenarios = ScenarioList.from_list("activity", ["reading", "running", "relaxing"])

        q_enjoy = QuestionLinearScale(
            question_name="enjoy_{{ scenario.activity }}", 
            question_text="On a scale from 1 to 5, how much do you enjoy {{ scenario.activity }}?",
            question_options=[1, 2, 3, 4, 5],
            option_labels={1:"Not at all", 5:"Very much"}
        )

        enjoy_questions = q_enjoy.loop(scenarios)
        
        # Basic validation that we got something back
        assert enjoy_questions is not None
        
    except Exception as e:
        pytest.fail(f"Exception was raised: {e}") 