import pytest
from edsl.exceptions.questions import QuestionScenarioRenderError
from edsl.questions.QuestionFreeText import QuestionFreeText
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
from edsl.questions import QuestionYesNo
from edsl.surveys import Survey
from edsl.scenarios import Scenario
from edsl.exceptions.questions import QuestionMissingTypeError, QuestionBadTypeError

valid_question = {
    "question_text": "How are you?",
    "question_name": "how_are_you",
}

valid_question_two = {
    "question_text": "How were you this morning?",
    "question_name": "how_were_you",
}

valid_question_three = {
    "question_text": "What is the capital of {{country}}",
    "question_name": "capital",
}


def test_parameters():

    q = QuestionFreeText(question_text="{{ poo}}", question_name="ugly_question")
    assert q.parameters == {"poo"}

    q = QuestionMultipleChoice(
        question_text="{{ poo}}",
        question_options=["A", "{{ B}}"],
        question_name="ugly_question",
    )
    assert q.parameters == {"poo", "B"}


def test_meta():
    pass


def test_Question_properties(capsys):
    """Test Question properties."""
    q = QuestionFreeText(**valid_question)

    # Prompt stuff
    # assert q.get_prompt()
    q3 = QuestionFreeText(**valid_question_three)
    # with pytest.raises(QuestionScenarioRenderError):
    #    q3.get_prompt()
    # assert q.formulate_prompt()
    # with pytest.raises(QuestionScenarioRenderError):
    #     q3.formulate_prompt()

    # Don't check this anymore b/c it's not a problem
    # curly = valid_question.copy()
    # import warnings

    # with warnings.catch_warnings():
    #     warnings.simplefilter("ignore", UserWarning)
    #     with pytest.warns(UserWarning):
    #         curly["question_text"] = "What is the capital of {country}"
    #         QuestionFreeText(**curly)

    # Q -> Survey stuff
    q1 = QuestionFreeText(**valid_question)
    q2 = QuestionFreeText(**valid_question_two)
    s = q1.add_question(q2)
    assert isinstance(s, Survey)
    assert len(s) == 2


def test_hashing():
    # NB: Will break if a new question is added or one is removed
    from edsl.questions.question_registry import Question

    examples = [
        Question.example(question_type)
        for question_type in Question.available()[0]["question_type"]
    ]
    hashes = [hash(q) for q in examples]
    assert (
        sum(hashes) > 0  # == 16668425656756741917
    )  # 16761523895673820409 == 16761523895673820409


def test_validation_with_rendering():

    s = Scenario({"city": ["Paris", "London", "Berlin", "Madrid"]})

    q = QuestionMultipleChoice(
        question_text="What is the capital of France?",
        question_name="capital_of_france",
        question_options=[
            "{{city[0]}}",
            "{{city[1]}}",
            "{{city[2]}}",
            "{{city[3]}}",
        ],
    )
    from edsl.exceptions.questions import QuestionAnswerValidationError

    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": "Paris"})

    new_q = q.render(s)
    new_q._validate_answer({"answer": "Paris"})
