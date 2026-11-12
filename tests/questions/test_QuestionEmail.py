import pytest

from edsl import QuestionEmail
from edsl.questions.exceptions import QuestionAnswerValidationError


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("Sure! ann@acme.com", "ann@acme.com"),
        ("ann@acme.com.", "ann@acme.com"),
        ("`ann@x.com`", "ann@x.com"),
        ("``ann@x.com``", "ann@x.com"),
        ("'`ann@x.com`'", "ann@x.com"),
        ("'ann@x.com'", "ann@x.com"),
        ("Contact: !ann@example.com", "!ann@example.com"),
        ('"ann@x.com"', "ann@x.com"),
        ("mailto:ann@x.com", "ann@x.com"),
        ('{"answer": "ann@x.com"}', "ann@x.com"),
    ],
)
def test_email_question_recovers_address_from_reply(reply, expected):
    question = QuestionEmail(
        question_name="email_address", question_text="What is your email?"
    )

    result = question._validate_answer({"answer": reply})

    assert result["answer"] == expected


def test_email_question_rejects_reply_without_valid_address():
    question = QuestionEmail(
        question_name="email_address", question_text="What is your email?"
    )

    with pytest.raises(QuestionAnswerValidationError):
        question._validate_answer({"answer": "Please contact me at ann@invalid"})


def test_email_question_keeps_emailstr_normalization_behavior():
    question = QuestionEmail(
        question_name="email_address", question_text="What is your email?"
    )

    assert question._validate_answer({"answer": "BOB@EXAMPLE.COM"})["answer"] == (
        "BOB@example.com"
    )
    assert question._validate_answer({"answer": "Ann <ann@x.com>"})["answer"] == (
        "ann@x.com"
    )
