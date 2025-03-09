import pytest
from unittest.mock import Mock, create_autospec
from edsl.questions import QuestionFreeText, QuestionFunctional
from edsl.questions.QuestionFreeText import QuestionFreeText
from edsl.questions.compose_questions import compose_questions
from edsl.jobs import Jobs
from edsl.scenarios import Scenario
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
from edsl.questions.derived.QuestionYesNo import QuestionYesNo


def SillyFunction(scenario, agent_traits):
    "Makes no use of the agent traits"
    return scenario["a"] + scenario["b"]


def test_QuestionFunctional_construction_from_function():
    """Test QuestionFunctional construction from a function"""

    scenario_valid = Scenario({"a": 10, "b": 2})
    scenario_wrong = Scenario({"a": 10, "c": 2})
    # construction
    q = QuestionFunctional(
        question_name="add_two_numbers", question_text="functional", func=SillyFunction
    )
    assert q.question_name == "add_two_numbers"
    # assert q.func == SillyFunction
    assert "question_type" in q.to_dict()
    assert "functional" in q.to_dict()["question_type"]
    # unnecessary methods are not implemented
    assert q._translate_answer_code_to_answer(None, None) is None
    q.activate()

    with pytest.raises(NotImplementedError):
        q._simulate_answer()
    # answer_question_directly works well
    assert isinstance(q.answer_question_directly(scenario_valid), dict)
    assert isinstance(q.answer_question_directly(scenario_valid), dict)
    assert q.answer_question_directly(scenario_valid)["answer"] == 12
    assert q.answer_question_directly(scenario_valid)["answer"] == 12
    assert q.answer_question_directly(scenario_valid)["comment"] is None
    assert q.answer_question_directly(scenario_valid)["comment"] is None
    # make sure by() works
    assert isinstance(q.by(scenario_valid), Jobs)
    assert isinstance(q.by(scenario_valid), Jobs)
    # I'm not testing run because it calls the LLM, which will be tested elsewhere
    # But if you'd like to take a look, run the below:
    # >> results = q.by(scenario_valid).run()
    # >> print(results)
    # I'll test whether incorrect scenarios throw an error
    # with pytest.raises(JobsRunError):
    #     assert q.by(scenario_wrong).run()

    # construction of a new class using QuestionFunctional
    class QuestionAddTwoNumbers(QuestionFunctional):
        def __init__(self, question_name, question_text):
            super().__init__(
                question_name=question_name,
                func=SillyFunction,
                question_text=question_text,
            )

    q = QuestionAddTwoNumbers(
        question_name="add_two_numbers", question_text="functional"
    )
    assert q.question_name == "add_two_numbers"
    # assert q.func == SillyFunction
    assert isinstance(q.by(scenario_valid), Jobs)
    assert isinstance(q.by(scenario_valid), Jobs)
    # I'll test whether incorrect scenarios throw an error
    # with pytest.raises(JobsRunError):
    #     assert q.by(scenario_wrong).run()


# Disabled because QuestionFunctional doesn't support nested functions as func paramter
# and also the code has to be refactor to work with this issue
def QuestionFunctional_construction_from_Questions():
    """This will use the compose_questions function"""

    # correct construction
    q1 = QuestionFreeText(
        question_text="What is the capital of {{country}}", question_name="capital"
    )
    q2 = QuestionFreeText(
        question_text="What is the population of {{capital}}",
        question_name="population",
    )
    q3 = compose_questions(q1, q2)
    assert q3.question_name == "capital_population"
    assert q3.func.__name__ == "combo"
    assert "question_type" in q3.to_dict()
    assert "functional" in q3.to_dict()["question_type"]
    # you can also use the __add__ method from Question
    assert q1 + q2

    # incorrect construction
    q1 = QuestionFreeText(
        question_text="What is the capital of {{country}}", question_name="capital"
    )
    q2 = QuestionFreeText(
        question_text="What is the population of {{city}}",
        question_name="population",
    )
    with pytest.raises(ValueError):
        q3 = compose_questions(q1, q2)


@pytest.fixture
def mock_questions_factory():
    def _create_mock_questions(
        question_name1="capital",
        question_name2="population",
        question_text2="What is the population of {{capital}}",
    ):
        # Create mock Question objects with autospec
        q1 = create_autospec(
            QuestionFreeText, instance=True, question_name=question_name1
        )
        q2 = create_autospec(
            QuestionFreeText, instance=True, question_name=question_name2
        )

        # Manually set the question_text attribute
        q2.question_text = question_text2

        # Create mocks for Jobs and Results objects
        mock_jobs1 = Mock()
        mock_jobs2 = Mock()
        mock_results1 = Mock()
        mock_results2 = Mock()

        # Set up the first chain: q1.by().by().run().select()
        q1.by.return_value = mock_jobs1
        mock_jobs1.by.return_value = mock_jobs1
        mock_jobs1.run.return_value = mock_results1
        mock_results1.select.return_value = ["Paris"]

        # Set up the second chain: q2.by().by().run().select()
        q2.by.return_value = mock_jobs2
        mock_jobs2.by.return_value = mock_jobs2
        mock_jobs2.run.return_value = mock_results2
        mock_results2.select.return_value = ["Large"]

        # Mock the get_prompt method for q2
        # q2.get_prompt.return_value = "What is the population of Paris"

        return q1, q2

    return _create_mock_questions


# Disabled because QuestionFunctional doesn't support nested functions as func paramter
# and also the code has to be refactor to work with this issue
def combo_function(mock_questions_factory):

    # correct construction
    q1, q2 = mock_questions_factory()
    composed_question = compose_questions(q1, q2)
    # Set up a mock scenario
    mock_scenario = Mock(spec=Scenario)
    # Execute the combo function
    result = composed_question.func(mock_scenario)
    # Assert that the result is as expected
    assert result == "Large"
    assert composed_question.question_name == "capital_population"
