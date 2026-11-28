import math

import pytest
from pydantic import ValidationError

from edsl import QuestionDate, QuestionDateTime, QuestionNumericalRange, Survey


def test_new_question_response_models_accept_shared_reasoning_field():
    cases = [
        (QuestionDate("d", "Date?"), "2026-05-20"),
        (QuestionDateTime("dt", "Datetime?"), "2026-05-20T14:30:00-04:00"),
        (QuestionNumericalRange("r", "Range?"), {"min": 2, "max": 8}),
    ]

    for question, answer in cases:
        response = question.response_model(
            answer=answer,
            comment=None,
            generated_tokens=None,
            reasoning_summary=None,
        )
        assert response.answer is not None


def test_date_rejects_malformed_calendar_dates():
    model = QuestionDate("date", "Choose a date?").response_model
    with pytest.raises(ValidationError):
        model(answer="2026-02-30")


def test_datetime_requires_offset_and_compares_bounds_as_instants():
    model = QuestionDateTime(
        "datetime",
        "Choose a time?",
        min_datetime="2026-05-20T12:00:00+02:00",
        max_datetime="2026-05-20T13:00:00+02:00",
    ).response_model

    assert model(answer="2026-05-20T10:00:00Z").answer == "2026-05-20T10:00:00+00:00"
    assert model(answer="2026-05-20T11:00:00Z").answer == "2026-05-20T11:00:00+00:00"
    with pytest.raises(ValidationError):
        model(answer="2026-05-20T09:59:59Z")
    with pytest.raises(ValidationError):
        model(answer="2026-05-20T12:30:00")


def test_date_bounds_survive_serialization_duplication_and_survey_draw():
    date_question = QuestionDate(
        "date", "Choose a date?", min_date="2026-01-01", max_date="2026-12-31"
    )
    datetime_question = QuestionDateTime(
        "datetime",
        "Choose a time?",
        min_datetime="2026-01-01T00:00:00Z",
        max_datetime="2026-12-31T23:59:59Z",
    )

    assert date_question.to_dict()["min_date"] == "2026-01-01"
    assert date_question.duplicate().max_date == "2026-12-31"
    assert Survey([date_question]).draw().questions[0].min_date == "2026-01-01"
    assert datetime_question.to_dict()["min_datetime"] == "2026-01-01T00:00:00+00:00"
    assert datetime_question.duplicate().max_datetime == "2026-12-31T23:59:59+00:00"


@pytest.mark.parametrize("endpoint", [math.nan, math.inf, -math.inf])
def test_numerical_range_rejects_non_finite_endpoints(endpoint):
    model = QuestionNumericalRange("range", "Choose a range?").response_model
    with pytest.raises(ValidationError):
        model(answer={"min": endpoint, "max": 8})


def test_numerical_range_rejects_reversed_endpoints():
    model = QuestionNumericalRange("range", "Choose a range?").response_model
    with pytest.raises(ValidationError):
        model(answer={"min": 9, "max": 8})
