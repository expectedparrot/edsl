"""Pydantic models for humanize survey question schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Type, Union

from pydantic import BaseModel, ValidationError

from ..questions import QuestionBase

from .exceptions import HumanizeSchemaValidationError

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..surveys.survey import QuestionType


class SurveyHumanizeSchema(BaseModel):
    """Humanize options for the survey (e.g. custom styling)."""

    custom_css: Optional[str] = None


class FreeTextHumanizeSchema(BaseModel):
    """Humanize options for the free text question type."""

    optional: bool = False


class BudgetHumanizeSchema(BaseModel):
    """Humanize options for the budget question type."""

    optional: bool = False


class CheckboxHumanizeSchema(BaseModel):
    """Humanize options for the checkbox question type."""

    optional: bool = False


class ComputeHumanizeSchema(BaseModel):
    """Humanize options for the compute question type (no optionality)."""

    pass


class InterviewHumanizeSchema(BaseModel):
    """Humanize options for the interview question type."""

    optional: bool = False


class LikertHumanizeSchema(BaseModel):
    """Humanize options for the likert question type."""

    optional: bool = False


class LinearScaleHumanizeSchema(BaseModel):
    """Humanize options for the linear scale question type."""

    optional: bool = False


class ListHumanizeSchema(BaseModel):
    """Humanize options for the list question type."""

    optional: bool = False


class MatrixHumanizeSchema(BaseModel):
    """Humanize options for the matrix question type."""

    optional: bool = False


class MultipleChoiceHumanizeSchema(BaseModel):
    """Humanize options for the multiple choice question type."""

    optional: bool = False


class MultipleChoiceWithOtherHumanizeSchema(BaseModel):
    """Humanize options for the multiple choice with other question type."""

    optional: bool = False


class NumericalHumanizeSchema(BaseModel):
    """Humanize options for the numerical question type."""

    optional: bool = False


class RankHumanizeSchema(BaseModel):
    """Humanize options for the rank question type."""

    optional: bool = False


class TopKHumanizeSchema(BaseModel):
    """Humanize options for the top k question type."""

    optional: bool = False


class YesNoHumanizeSchema(BaseModel):
    """Humanize options for the yes/no question type."""

    optional: bool = False


HumanizeQuestionSchema = Union[
    FreeTextHumanizeSchema,
    BudgetHumanizeSchema,
    CheckboxHumanizeSchema,
    ComputeHumanizeSchema,
    InterviewHumanizeSchema,
    LikertHumanizeSchema,
    LinearScaleHumanizeSchema,
    ListHumanizeSchema,
    MatrixHumanizeSchema,
    MultipleChoiceHumanizeSchema,
    MultipleChoiceWithOtherHumanizeSchema,
    NumericalHumanizeSchema,
    RankHumanizeSchema,
    TopKHumanizeSchema,
    YesNoHumanizeSchema,
]


class HumanizeSchema(BaseModel):
    """Humanize options per question; maps question names to their schema."""

    questions: dict[str, HumanizeQuestionSchema] = {}
    survey: Optional[SurveyHumanizeSchema] = None


# Map each EDSL question_type to the humanize schema class that must be used
# for that question. Validation uses this to model_validate each schema entry
# against the correct class.
QUESTION_TYPE_TO_HUMANIZE_CLASS: Dict[str, Type[BaseModel]] = {
    "free_text": FreeTextHumanizeSchema,
    "budget": BudgetHumanizeSchema,
    "checkbox": CheckboxHumanizeSchema,
    "compute": ComputeHumanizeSchema,
    "interview": InterviewHumanizeSchema,
    "likert_five": LikertHumanizeSchema,
    "linear_scale": LinearScaleHumanizeSchema,
    "list": ListHumanizeSchema,
    "matrix": MatrixHumanizeSchema,
    "multiple_choice": MultipleChoiceHumanizeSchema,
    "multiple_choice_with_other": MultipleChoiceWithOtherHumanizeSchema,
    "numerical": NumericalHumanizeSchema,
    "rank": RankHumanizeSchema,
    "top_k": TopKHumanizeSchema,
    "yes_no": YesNoHumanizeSchema,
}


def validate_humanize_schema(
    survey: Survey,
    humanize_schema: Dict[str, Any],
) -> None:
    """
    Validate a humanize schema against the survey.

    Validates overall structure with HumanizeSchema, then for each question in
    the schema validates that entry with the humanize model class for that
    question's type (e.g. free_text -> FreeTextHumanizeSchema).     Raises HumanizeSchemaValidationError if the schema is invalid, references a
    question not in the survey, an instruction, or an unsupported question type,
    or if a question's entry does not validate against the correct model.
    """
    try:
        validated_schema = HumanizeSchema.model_validate(humanize_schema)
    except ValidationError as e:
        raise HumanizeSchemaValidationError(str(e)) from e

    questions: Dict[str, QuestionType] = survey.question_names_to_questions()
    raw_questions = humanize_schema.get("questions") or {}

    # For each question in the schema, validate the raw entry against the
    # humanize class for that question's type (e.g. free_text ->
    # FreeTextHumanizeSchema).
    for question_name in validated_schema.questions:
        if question_name not in questions:
            raise HumanizeSchemaValidationError(
                f"Humanize schema references question {question_name!r}, "
                "which is not in the survey."
            )
        q: QuestionType = questions[question_name]
        if not isinstance(q, QuestionBase):
            raise HumanizeSchemaValidationError(
                f"Humanize schema references {question_name!r}, which is an "
                "instruction, not a question. Humanize schema can only be "
                "applied to questions."
            )
        question_type: str = q.question_type
        model_class = QUESTION_TYPE_TO_HUMANIZE_CLASS.get(question_type)
        if model_class is None:
            raise HumanizeSchemaValidationError(
                f"Question {question_name!r} has type {question_type!r}, which "
                "is not supported for humanize schema."
            )
        raw_entry = raw_questions.get(question_name)
        try:
            model_class.model_validate(raw_entry)
        except ValidationError as e:
            raise HumanizeSchemaValidationError(str(e)) from e
