import pytest

from edsl import Question, QuestionURL
from edsl.questions import QuestionBase
from edsl.questions.exceptions import QuestionAnswerValidationError


def test_question_url_construction_and_registration():
    question = QuestionURL(
        question_name="source", question_text="What is the source URL?"
    )

    assert question.question_type == "url"
    assert isinstance(
        Question("url", question_name="source", question_text="Source?"),
        QuestionURL,
    )
    assert "url" in Question.list_question_types()


def test_question_url_accepts_valid_urls_as_strings():
    question = QuestionURL.example()

    for url in (
        "https://example.com",
        "https://example.com/path?q=value#fragment",
        "ftp://files.example.com/archive.zip",
    ):
        response = question._validate_answer({"answer": url})
        assert response["answer"] == url
        assert isinstance(response["answer"], str)


@pytest.mark.parametrize(
    "answer", ["example.com", "/relative/path", "not a url", "", None, 42]
)
def test_question_url_rejects_invalid_urls(answer):
    with pytest.raises(QuestionAnswerValidationError):
        QuestionURL.example()._validate_answer({"answer": answer})


def test_question_url_serialization_round_trip():
    question = QuestionURL(
        question_name="source", question_text="What is the source URL?"
    )

    restored = QuestionBase.from_dict(question.to_dict())

    assert isinstance(restored, QuestionURL)
    assert restored == question
    assert restored.to_dict()["question_type"] == "url"


def test_question_url_html_uses_url_input():
    assert 'type="url"' in QuestionURL.example().question_html_content
