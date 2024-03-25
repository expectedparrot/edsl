import pytest
from edsl.exceptions import QuestionScenarioRenderError
from edsl.questions import QuestionFreeText
from edsl.surveys import Survey

from edsl.exceptions.questions import QuestionMissingTypeError, QuestionBadTypeError

valid_question = {
    "question_text": "How are you?",
    "allow_nonresponse": False,
    "question_name": "how_are_you",
}

valid_question_two = {
    "question_text": "How were you this morning?",
    "allow_nonresponse": False,
    "question_name": "how_were_you",
}

valid_question_three = {
    "question_text": "What is the capital of {{country}}",
    "question_name": "capital",
}


def test_meta():
    from edsl.questions.QuestionBase import QuestionBase

    class ABCMixins:
        def _validate_answer(self, answer: dict[str, str]):
            pass

        def _validate_response(self, response):
            pass

        def _translate_answer_code_to_answer(self):
            pass

        def _simulate_answer(self, human_readable=True) -> dict:
            pass

    with pytest.raises(QuestionMissingTypeError):

        class BadQuestion(ABCMixins, QuestionBase):
            pass

    with pytest.raises(QuestionBadTypeError):

        class BadQuestion(ABCMixins, QuestionBase):
            question_type = "poop"


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
    curly["question_text"] = "What is the capital of {country}"
    # make sure that when you initialize curly, it outputs a string that contains "WARNING"
    # it's not a warning, just a string printed, so you have to check capsys
    QuestionFreeText(**curly)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out

    # Q -> Survey stuff
    q1 = QuestionFreeText(**valid_question)
    q2 = QuestionFreeText(**valid_question_two)
    s = q1.add_question(q2)
    assert isinstance(s, Survey)
    assert len(s) == 2
