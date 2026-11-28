"""Date and timezone-aware datetime question types."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator, model_validator

from .decorators import inject_exception
from .descriptors import QuestionTextDescriptor
from .exceptions import QuestionCreationValidationError
from . import markdown_layout as md
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class DateResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [({"answer": "2026-05-20"}, {})]
    invalid_examples = [({"answer": "May 20, 2026"}, {}, "ISO date")]


class DateTimeResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [({"answer": "2026-05-20T14:30:00-04:00"}, {})]
    invalid_examples = [({"answer": "2026-05-20T14:30:00"}, {}, "timezone offset")]


def _parse_date(value: str) -> date:
    if not isinstance(value, str):
        raise ValueError("Date answers must be ISO 8601 date strings (YYYY-MM-DD).")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date answers must use YYYY-MM-DD format.") from exc
    if parsed.isoformat() != value:
        raise ValueError("Date answers must use canonical YYYY-MM-DD format.")
    return parsed


def _parse_datetime(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(
            "Datetime answers must be ISO 8601 strings with a timezone offset."
        )
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Datetime answers must use ISO 8601 format.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            "Datetime answers must include a timezone offset, such as Z or +02:00."
        )
    return parsed


def _date_bound(value: Optional[str], name: str) -> Optional[date]:
    if value is None:
        return None
    try:
        return _parse_date(value)
    except ValueError as exc:
        raise QuestionCreationValidationError(
            f"{name} must be an ISO date string (YYYY-MM-DD)."
        ) from exc


def _datetime_bound(value: Optional[str], name: str) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return _parse_datetime(value)
    except ValueError as exc:
        raise QuestionCreationValidationError(
            f"{name} must be an ISO 8601 datetime with a timezone offset."
        ) from exc


def create_date_response(min_date: Optional[str], max_date: Optional[str]):
    lower = _date_bound(min_date, "min_date")
    upper = _date_bound(max_date, "max_date")
    if lower and upper and lower > upper:
        raise QuestionCreationValidationError("min_date cannot be after max_date.")

    class DateResponse(BaseModel):
        answer: StrictStr
        comment: Optional[str] = None
        generated_tokens: Optional[str] = None
        reasoning_summary: Optional[str] = None
        model_config = ConfigDict(extra="forbid")

        @field_validator("answer")
        @classmethod
        def validate_answer(cls, value: str) -> str:
            return _parse_date(value).isoformat()

        @model_validator(mode="after")
        def validate_bounds(self):
            value = _parse_date(self.answer)
            if lower and value < lower:
                raise ValueError(f"Date must be on or after {lower.isoformat()}.")
            if upper and value > upper:
                raise ValueError(f"Date must be on or before {upper.isoformat()}.")
            return self

    return DateResponse


def create_datetime_response(min_datetime: Optional[str], max_datetime: Optional[str]):
    lower = _datetime_bound(min_datetime, "min_datetime")
    upper = _datetime_bound(max_datetime, "max_datetime")
    if lower and upper and lower > upper:
        raise QuestionCreationValidationError(
            "min_datetime cannot be after max_datetime."
        )

    class DateTimeResponse(BaseModel):
        answer: StrictStr
        comment: Optional[str] = None
        generated_tokens: Optional[str] = None
        reasoning_summary: Optional[str] = None
        model_config = ConfigDict(extra="forbid")

        @field_validator("answer")
        @classmethod
        def validate_answer(cls, value: str) -> str:
            return _parse_datetime(value).isoformat()

        @model_validator(mode="after")
        def validate_bounds(self):
            value = _parse_datetime(self.answer)
            if lower and value < lower:
                raise ValueError(f"Datetime must be on or after {lower.isoformat()}.")
            if upper and value > upper:
                raise ValueError(f"Datetime must be on or before {upper.isoformat()}.")
            return self

    return DateTimeResponse


class QuestionDate(QuestionBase):
    """Ask for a calendar date, returned as an ISO ``YYYY-MM-DD`` string.

    >>> q = QuestionDate("launch", "When does it launch?", min_date="2026-01-01")
    >>> q.response_model(answer="2026-05-20").answer
    '2026-05-20'
    """

    question_type = "date"
    question_text = QuestionTextDescriptor()
    response_validator_class = DateResponseValidator
    _response_model = None

    def __init__(
        self,
        question_name: str,
        question_text: str,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        lower = _date_bound(min_date, "min_date")
        upper = _date_bound(max_date, "max_date")
        if lower and upper and lower > upper:
            raise QuestionCreationValidationError("min_date cannot be after max_date.")
        self.question_name = question_name
        self.question_text = question_text
        self._min_date = lower.isoformat() if lower else None
        self._max_date = upper.isoformat() if upper else None
        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    def create_response_model(self):
        return create_date_response(self.min_date, self.max_date)

    @property
    def min_date(self) -> Optional[str]:
        return self._min_date

    @property
    def max_date(self) -> Optional[str]:
        return self._max_date

    def _simulate_answer(self) -> dict:
        lower = _date_bound(self.min_date, "min_date") or date(2000, 1, 1)
        upper = _date_bound(self.max_date, "max_date") or date(2030, 12, 31)
        if self.min_date is None and self.max_date is not None:
            lower = min(date(2000, 1, 1), upper)
        if self.max_date is None and self.min_date is not None:
            upper = max(date(2030, 12, 31), lower)
        span = (upper - lower).days
        from random import randint

        return {
            "answer": date.fromordinal(lower.toordinal() + randint(0, span)).isoformat()
        }

    def _markdown_answer(self, view):
        return "Enter a date" + md.bounds(self.min_date, self.max_date) + "."

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        return Template(
            '<input type="date" id="{{ name }}" name="{{ name }}" '
            '{% if min_date %}min="{{ min_date }}"{% endif %} '
            '{% if max_date %}max="{{ max_date }}"{% endif %}>'
        ).render(
            name=self.question_name, min_date=self.min_date, max_date=self.max_date
        )

    @classmethod
    @inject_exception
    def example(cls) -> "QuestionDate":
        return cls(
            question_name="start_date",
            question_text="What date should the project begin?",
            min_date="2026-01-01",
            max_date="2026-12-31",
        )


class QuestionDateTime(QuestionBase):
    """Ask for a timezone-aware datetime, returned as an ISO 8601 string.

    >>> q = QuestionDateTime("meeting", "When is the meeting?")
    >>> q.response_model(answer="2026-05-20T14:30:00-04:00").answer
    '2026-05-20T14:30:00-04:00'
    """

    question_type = "date_time"
    question_text = QuestionTextDescriptor()
    response_validator_class = DateTimeResponseValidator
    _response_model = None

    def __init__(
        self,
        question_name: str,
        question_text: str,
        min_datetime: Optional[str] = None,
        max_datetime: Optional[str] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        lower = _datetime_bound(min_datetime, "min_datetime")
        upper = _datetime_bound(max_datetime, "max_datetime")
        if lower and upper and lower > upper:
            raise QuestionCreationValidationError(
                "min_datetime cannot be after max_datetime."
            )
        self.question_name = question_name
        self.question_text = question_text
        self._min_datetime = lower.isoformat() if lower else None
        self._max_datetime = upper.isoformat() if upper else None
        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    def create_response_model(self):
        return create_datetime_response(self.min_datetime, self.max_datetime)

    @property
    def min_datetime(self) -> Optional[str]:
        return self._min_datetime

    @property
    def max_datetime(self) -> Optional[str]:
        return self._max_datetime

    def _simulate_answer(self) -> dict:
        from datetime import timedelta, timezone
        from random import randint

        lower = _datetime_bound(self.min_datetime, "min_datetime")
        upper = _datetime_bound(self.max_datetime, "max_datetime")
        baseline_lower = datetime(2000, 1, 1, tzinfo=timezone.utc)
        baseline_upper = datetime(2030, 12, 31, tzinfo=timezone.utc)
        if lower is None:
            lower = min(baseline_lower, upper) if upper else baseline_lower
        if upper is None:
            upper = max(baseline_upper, lower)
        lower_utc = lower.astimezone(timezone.utc)
        upper_utc = upper.astimezone(timezone.utc)
        seconds = max(0, int((upper_utc - lower_utc).total_seconds()))
        answer = lower_utc + timedelta(seconds=randint(0, seconds))
        return {"answer": answer.isoformat()}

    def _markdown_answer(self, view):
        return (
            "Enter a date and time"
            + md.bounds(self.min_datetime, self.max_datetime)
            + "."
        )

    @property
    def question_html_content(self) -> str:
        return (
            f'<input type="text" id="{self.question_name}" '
            f'name="{self.question_name}" '
            'placeholder="2026-05-20T14:30:00-04:00">'
        )

    @classmethod
    @inject_exception
    def example(cls) -> "QuestionDateTime":
        return cls(
            question_name="appointment_time",
            question_text="What time should the appointment begin? Include the timezone.",
            min_datetime="2026-05-20T09:00:00-04:00",
            max_datetime="2026-05-20T17:00:00-04:00",
        )
