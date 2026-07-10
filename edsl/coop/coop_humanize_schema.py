"""Pydantic models for humanize survey question schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Dict, Literal, Optional, Type, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from ..questions import QuestionBase

from .exceptions import HumanizeSchemaValidationError
from .voice_interview_languages import (
    DEFAULT_VOICE_INTERVIEW_LANGUAGE,
    normalize_voice_interview_language,
)

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..surveys.survey import QuestionType


class HumanizeSchemaBase(BaseModel):
    """Base for humanize schema models; forbids extra fields."""

    model_config = ConfigDict(extra="forbid")


class MCSubclassFormatSchema(HumanizeSchemaBase):
    """Display format for MC-style questions: radio list or dropdown."""

    type: Literal["radio", "dropdown"] = "radio"


class SurveyHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the survey (e.g. custom styling)."""

    custom_css: Optional[str] = None


class CommentConfig(HumanizeSchemaBase):
    """Configuration for the optional comment field on a question."""

    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FreeTextHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the free text question type."""

    optional: bool = False
    comment: Optional[CommentConfig] = None


class BudgetHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the budget question type."""

    optional: bool = False
    comment: Optional[CommentConfig] = None


class CheckboxHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the checkbox question type."""

    optional: bool = False
    comment: Optional[CommentConfig] = None


class ComputeHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the compute question type (no optionality)."""

    pass


class FileUploadHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the file upload question type."""

    optional: bool = False


class ChecklistItemSchema(HumanizeSchemaBase):
    """One checklist item the interviewer can tick off during the interview."""

    # Opaque token (the human-readable text lives in `label`/`instructions`).
    # Restricted to an identifier charset so it stays safe to interpolate into the
    # quoted prompt line `- id "{id}": ...` — a stray `"` would malform it.
    id: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=64,
            pattern=r"^[A-Za-z0-9_\-]+$",
        ),
    ]
    # Participant-facing — shown in the checklist UI.
    label: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    # Model-facing — the condition under which the model should check this item off.
    instructions: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class ManualChecklistItems(HumanizeSchemaBase):
    """Checklist items written by the survey author by hand.

    The starting set of a checklist (`ChecklistConfig.initial`),
    discriminated by ``type`` so a ``generated`` sibling (model-produced items)
    can join later as a ``Union[Manual, Generated]`` without reshaping stored
    configs — existing configs already carry ``type: "manual"``. ``manual`` is
    the only variant today.
    """

    type: Literal["manual"] = "manual"
    items: list[ChecklistItemSchema] = []  # may be empty

    @model_validator(mode="after")
    def _unique_item_ids(self) -> "ManualChecklistItems":
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Checklist item ids must be unique.")
        return self


class ChecklistConfig(HumanizeSchemaBase):
    """Checklist for a text interview.

    ``initial`` is the *starting* set — author-written (`manual`) today —
    kept as a discriminated union so a `generated` source can be added, and named
    "initial" (not "items") because runtime additions (model-added items) may
    later extend the list beyond this seed. Either evolution is additive: stored
    configs already carry the ``type`` discriminator, and the answer records
    additions as actions, so neither reshapes existing data.
    """

    initial: ManualChecklistItems = Field(default_factory=ManualChecklistItems)
    # Whether/when the participant sees the checklist. The model always sees it
    # (it's in the system prompt) and the author sees the folded final state in
    # results; this axis is only about the participant.
    # - "visible": the floating panel is shown during the interview (today's
    #   behavior, hence the default — keeps the ChecklistConfig wrap
    #   behavior-preserving).
    # - "hidden": the participant never sees it; a pure interviewer instrument
    #   (status is still folded internally, just not shown).
    participant_visibility: Literal["hidden", "visible"] = "visible"


class InterviewMarkedCompleteMessage(HumanizeSchemaBase):
    """A message to surface on the turn the interviewer first marks the interview
    complete (the ``interview_complete`` flag's false->true transition).

    When ``end_policy.interview_marked_complete_message`` is None, that turn keeps
    the model's own generated text. When set, ``method`` decides how this
    ``message`` relates to that text — today only ``replace`` (show this
    ``message`` instead of the model's text for that one turn).
    """

    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2500),
    ]
    # How `message` relates to the model's text on the marking turn. Only
    # "replace" today; "prepend"/"append" can join this literal later.
    method: Literal["replace"] = "replace"


class RespondentEndPolicy(HumanizeSchemaBase):
    """The participant ends the interview themselves; the End Interview button is
    always available. The default, matching prior behavior."""

    control: Literal["respondent"] = "respondent"


class InterviewerGatedEndPolicy(HumanizeSchemaBase):
    """The participant can only end once the model signals (via the structured
    ``interview_complete`` flag) that its goals are met — the signal opens the
    gate to the End Interview button."""

    control: Literal["interviewer_gated"] = "interviewer_gated"

    # Optional message for the turn the interviewer first marks the interview
    # complete (the flag's false->true transition). None keeps the model's own
    # text for that turn. Lives only here because it's meaningless without the
    # gate.
    interview_marked_complete_message: Optional[InterviewMarkedCompleteMessage] = None


# How a text interview is allowed to end, discriminated by ``control`` so each
# mode carries only the fields it can act on. New modes/guards (allow_withdraw /
# max_turns / min_turns) join as additional variants or additive fields without
# reshaping existing ones.
EndPolicy = Annotated[
    Union[RespondentEndPolicy, InterviewerGatedEndPolicy],
    Field(discriminator="control"),
]


class TextInterviewConfig(HumanizeSchemaBase):
    """Configuration specific to text-mode interviews."""

    language: str = DEFAULT_VOICE_INTERVIEW_LANGUAGE
    interviewer_name: Annotated[
        Optional[str],
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ] = None
    end_interview_message: Annotated[
        Optional[str],
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2500),
    ] = None
    checklist: Optional[ChecklistConfig] = None
    end_policy: EndPolicy = Field(default_factory=RespondentEndPolicy)

    @field_validator("language", mode="before")
    @classmethod
    def _validate_language(cls, v: object) -> str:
        return normalize_voice_interview_language(v)


class VoiceInterviewConfig(HumanizeSchemaBase):
    """Configuration specific to voice-mode interviews."""

    # The spoken language for the voice interview. Stored as a lowercase id
    # (e.g. "english"); the before-validator normalizes case/whitespace, maps
    # None/blank to the default, and rejects unsupported languages.
    language: str = DEFAULT_VOICE_INTERVIEW_LANGUAGE

    @field_validator("language", mode="before")
    @classmethod
    def _validate_language(cls, v: object) -> str:
        return normalize_voice_interview_language(v)


class InterviewHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the interview question type."""

    optional: bool = False
    interview_mode: Literal["text", "voice", "both"] = "text"
    voice_interview_config: Optional[VoiceInterviewConfig] = None
    text_interview_config: Optional[TextInterviewConfig] = None


class LikertHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the likert question type."""

    optional: bool = False
    format: MCSubclassFormatSchema = Field(default_factory=MCSubclassFormatSchema)
    comment: Optional[CommentConfig] = None


class LinearScaleHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the linear scale question type."""

    optional: bool = False
    format: MCSubclassFormatSchema = Field(default_factory=MCSubclassFormatSchema)
    comment: Optional[CommentConfig] = None


class ListHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the list question type."""

    optional: bool = False
    comment: Optional[CommentConfig] = None


class MatrixHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the matrix question type."""

    optional: bool = False
    comment: Optional[CommentConfig] = None


class MultipleChoiceCustomValidation(HumanizeSchemaBase):
    """Custom validation for multiple choice: require a specific answer (e.g. select_exact_answer)."""

    select_exact_answer: Optional[str] = None


class MultipleChoiceHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the multiple choice question type."""

    optional: bool = False
    format: MCSubclassFormatSchema = Field(default_factory=MCSubclassFormatSchema)
    custom_validation: Optional[MultipleChoiceCustomValidation] = None
    comment: Optional[CommentConfig] = None


class MultipleChoiceWithOtherHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the multiple choice with other question type."""

    optional: bool = False
    comment: Optional[CommentConfig] = None


class NumericalFormatInputSchema(HumanizeSchemaBase):
    """Display as a number input field."""

    type: Literal["input"] = "input"


class NumericalFormatSliderSchema(HumanizeSchemaBase):
    """Display as a slider with min, max, and step."""

    type: Literal["slider"] = "slider"
    min: float = 0.0
    max: float = 100.0
    step: float = 1.0

    @model_validator(mode="after")
    def check_slider_bounds(self) -> "NumericalFormatSliderSchema":
        if self.min >= self.max:
            raise ValueError("Slider minimum must be less than maximum.")
        if self.step <= 0:
            raise ValueError("Slider step must be positive.")
        if self.step > (self.max - self.min):
            raise ValueError("Slider step must not exceed (max - min).")
        return self


NumericalFormatSchema = Union[
    NumericalFormatInputSchema,
    NumericalFormatSliderSchema,
]


class NumericalHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the numerical question type."""

    optional: bool = False
    format: NumericalFormatSchema = Field(default_factory=NumericalFormatInputSchema)
    comment: Optional[CommentConfig] = None


class RankHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the rank question type."""

    optional: bool = False
    comment: Optional[CommentConfig] = None


class TopKHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the top k question type."""

    optional: bool = False
    comment: Optional[CommentConfig] = None


class YesNoHumanizeSchema(HumanizeSchemaBase):
    """Humanize options for the yes/no question type."""

    optional: bool = False
    format: MCSubclassFormatSchema = Field(default_factory=MCSubclassFormatSchema)
    comment: Optional[CommentConfig] = None


HumanizeQuestionSchema = Union[
    FreeTextHumanizeSchema,
    BudgetHumanizeSchema,
    CheckboxHumanizeSchema,
    ComputeHumanizeSchema,
    FileUploadHumanizeSchema,
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


class HumanizeSchema(HumanizeSchemaBase):
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
    "file_upload": FileUploadHumanizeSchema,
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
