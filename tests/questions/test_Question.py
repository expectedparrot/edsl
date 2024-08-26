import pytest
from edsl.exceptions import QuestionScenarioRenderError
from edsl.questions import QuestionFreeText
from edsl.surveys import Survey

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
    from edsl import QuestionFreeText

    q = QuestionFreeText(question_text="{{ poo}}", question_name="ugly_question")
    assert q.parameters == {"poo"}

    from edsl import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_text="{{ poo}}",
        question_options=["A", "{{ B}}"],
        question_name="ugly_question",
    )
    assert q.parameters == {"poo", "B"}


def test_meta():
    pass

    # from edsl.questions.QuestionBase import QuestionBase

    # class ABCMixins:
    #     _response_model = None
    #     response_validator_class = None

    #     def _validate_answer(self, answer: dict[str, str]):
    #         pass

    #     def _validate_response(self, response):
    #         pass

    #     def _translate_answer_code_to_answer(self):
    #         pass

    #     def _simulate_answer(self, human_readable=True) -> dict:
    #         pass

    # with pytest.raises(QuestionMissingTypeError):

    #     class BadQuestion(ABCMixins, QuestionBase):
    #         pass

    # with pytest.raises(QuestionBadTypeError):

    #     class BadQuestion(ABCMixins, QuestionBase):
    #         question_type = "poop"


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
    curly = valid_question.copy()
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with pytest.warns(UserWarning):
            curly["question_text"] = "What is the capital of {country}"
            QuestionFreeText(**curly)

    # Q -> Survey stuff
    q1 = QuestionFreeText(**valid_question)
    q2 = QuestionFreeText(**valid_question_two)
    s = q1.add_question(q2)
    assert isinstance(s, Survey)
    assert len(s) == 2


def test_hashing():
    # NB: Will break if a new question is added or one is removed
    from edsl import Question

    examples = [
        Question.example(question_type) for question_type in Question.available()
    ]
    hashes = [hash(q) for q in examples]
    assert (
        sum(hashes) > 0  # == 16668425656756741917
    )  # 16761523895673820409 == 16761523895673820409
